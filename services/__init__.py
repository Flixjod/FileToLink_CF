"""
File streaming service with range request support and performance optimizations
Uses get_messages and stream_media instead of download_media (no 20MB limit!)
"""
import re
import logging
from flask import Response, request
from pyrogram import Client
from database import Database
from config import Config
from constants import *
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class StreamingService:
    """Handle file streaming with range request support using Pyrogram's stream_media"""
    
    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db = db
    
    def parse_range_header(self, range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
        """Parse HTTP Range header and return (start, end) tuple"""
        if not range_header:
            return None
        
        try:
            # Parse "bytes=start-end" format
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if not match:
                return None
            
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            
            # Validate range
            if start >= file_size or end >= file_size or start > end:
                return None
            
            return (start, end)
        except Exception as e:
            logger.error(f"Range parsing error: {e}")
            return None
    
    async def stream_file(self, file_hash: str, is_download: bool = False):
        """
        Stream file with range request support using get_messages (no 20MB limit!)
        
        Args:
            file_hash: Hashed file identifier
            is_download: If True, set Content-Disposition to attachment
        
        Returns:
            Flask Response object
        """
        try:
            # Get file info from database using hash
            file_data = await self.db.get_file_by_hash(file_hash)
            
            if not file_data:
                return {"error": "File not found"}, HTTP_NOT_FOUND
            
            # Check bandwidth
            stats = await self.db.get_bandwidth_stats()
            max_bandwidth = Config.get("max_bandwidth", 107374182400)
            if stats["total_bandwidth"] >= max_bandwidth:
                return {"error": "Bandwidth limit exceeded"}, HTTP_SERVICE_UNAVAILABLE
            
            # Get message using get_messages (works for all file sizes!)
            message = await self.bot.get_messages(Config.DUMP_CHAT_ID, int(file_data['message_id']))
            if not message:
                return {"error": "File not found in channel"}, HTTP_NOT_FOUND
            
            # Extract file object
            file_obj = None
            if message.document:
                file_obj = message.document
            elif message.video:
                file_obj = message.video
            elif message.audio:
                file_obj = message.audio
            elif message.photo:
                file_obj = message.photo
            else:
                return {"error": "Unsupported file type"}, HTTP_BAD_REQUEST
            
            file_size = file_data['file_size']
            file_name = file_data['file_name']
            
            # Check if range request
            range_header = request.headers.get('Range')
            range_data = self.parse_range_header(range_header, file_size) if range_header else None
            
            if range_data:
                start, end = range_data
                status_code = HTTP_PARTIAL_CONTENT
                content_length = end - start + 1
            else:
                start, end = 0, file_size - 1
                status_code = HTTP_OK
                content_length = file_size
            
            # Increment download counter (async, don't wait)
            import asyncio
            asyncio.create_task(self.db.increment_downloads(file_data['message_id'], content_length))
            
            # Use Pyrogram's stream_media for efficient streaming (no download to memory!)
            # This streams directly from Telegram servers
            def generate():
                """Synchronous generator for Flask Response"""
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    bytes_sent = 0
                    offset = start
                    limit = content_length
                    
                    # Stream file in chunks
                    async def async_stream():
                        nonlocal bytes_sent
                        async for chunk in self.bot.stream_media(message, offset=offset, limit=limit):
                            if chunk and bytes_sent < content_length:
                                bytes_to_send = min(len(chunk), content_length - bytes_sent)
                                yield chunk[:bytes_to_send]
                                bytes_sent += bytes_to_send
                                if bytes_sent >= content_length:
                                    break
                    
                    # Run async generator in sync context
                    async_gen = async_stream()
                    while True:
                        try:
                            chunk = loop.run_until_complete(async_gen.__anext__())
                            yield chunk
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()
            
            # Determine MIME type
            mime_type = file_data.get('mime_type') or MIME_TYPE_MAP.get(file_data.get('file_type'), 'application/octet-stream')
            
            # Build response
            response = Response(generate(), mimetype=mime_type, status=status_code)
            
            # Set headers
            disposition = 'attachment' if is_download else 'inline'
            response.headers['Content-Disposition'] = f'{disposition}; filename="{file_name}"'
            response.headers['Content-Length'] = str(content_length)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = CACHE_CONTROL_PUBLIC
            
            # Range headers for partial content
            if status_code == HTTP_PARTIAL_CONTENT:
                response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            
            return response
            
        except ValueError as e:
            logger.error(f"Invalid file hash: {e}")
            return {"error": "Invalid file hash"}, HTTP_BAD_REQUEST
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            return {"error": str(e)}, HTTP_INTERNAL_ERROR
