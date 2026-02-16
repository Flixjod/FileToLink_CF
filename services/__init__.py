"""
File streaming service with range request support and performance optimizations
"""
import re
import logging
from flask import Response, request
from pyrogram import Client
from database import Database
from config import Config
from constants import *
from typing import Tuple, Optional
from io import BytesIO

logger = logging.getLogger(__name__)


class StreamingService:
    """Handle file streaming with range request support"""
    
    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db = db
    
    async def get_file_message(self, message_id: int):
        """Get message from bot channel"""
        try:
            message = await self.bot.get_messages(Config.BOT_CHANNEL, int(message_id))
            return message
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
    
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
        Stream file with support for range requests
        
        Args:
            file_hash: Hashed file identifier
            is_download: If True, set Content-Disposition to attachment
        
        Returns:
            Flask Response object
        """
        from utils import Cryptic
        
        try:
            # Decode and get file info
            message_id = Cryptic.dehash_file_id(file_hash)
            file_data = await self.db.get_file(message_id)
            
            if not file_data:
                return {"error": "File not found"}, HTTP_NOT_FOUND
            
            # Check bandwidth
            stats = await self.db.get_bandwidth_stats()
            if stats["total_bandwidth"] >= Config.MAX_BANDWIDTH:
                return {"error": "Bandwidth limit exceeded"}, HTTP_SERVICE_UNAVAILABLE
            
            # Get Telegram message
            message = await self.get_file_message(message_id)
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
            
            # Download file (Pyrogram handles this efficiently)
            # For large files, we'll use iter_download for streaming
            file_stream = await self.bot.download_media(message, in_memory=True)
            
            if not file_stream:
                return {"error": "Failed to download file"}, HTTP_INTERNAL_ERROR
            
            # Increment download counter (async, don't wait)
            import asyncio
            asyncio.create_task(self.db.increment_downloads(message_id, file_size))
            
            # Generate streaming response
            def generate():
                if isinstance(file_stream, BytesIO):
                    file_stream.seek(start)
                    remaining = content_length
                    
                    while remaining > 0:
                        chunk_size = min(Config.STREAM_CHUNK_SIZE, remaining)
                        chunk = file_stream.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
                else:
                    # File path - read from disk
                    with open(file_stream, 'rb') as f:
                        f.seek(start)
                        remaining = content_length
                        
                        while remaining > 0:
                            chunk_size = min(Config.STREAM_CHUNK_SIZE, remaining)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk
            
            # Determine MIME type
            mime_type = file_data.get('file_type', 'application/octet-stream')
            if mime_type in MIME_TYPE_MAP:
                mime_type = MIME_TYPE_MAP[mime_type]
            
            # Build response
            response = Response(generate(), mimetype=mime_type, status=status_code)
            
            # Set headers
            disposition = 'attachment' if is_download else 'inline'
            response.headers['Content-Disposition'] = f'{disposition}; filename=\"{file_name}\"'
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
