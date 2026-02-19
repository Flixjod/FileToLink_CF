"""
File streaming service with range-request support.
Uses Pyrogram's stream_media (no 20 MB limit, no download to disk).
Fully async – built on aiohttp StreamResponse.
"""
import re
import asyncio
import logging
from typing import Optional, Tuple

from aiohttp import web
from pyrogram import Client

from database import Database
from config import Config

logger = logging.getLogger(__name__)


def _parse_range(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """Parse HTTP Range header → (start, end) or None."""
    if not range_header:
        return None
    match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return None
    start = int(match.group(1))
    end   = int(match.group(2)) if match.group(2) else file_size - 1
    if start >= file_size or end >= file_size or start > end:
        return None
    return start, end


class StreamingService:
    """Handle file streaming with range-request support via Pyrogram stream_media."""

    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db  = db

    async def stream_file(
        self,
        request: web.Request,
        file_hash: str,
        is_download: bool = False,
    ) -> web.StreamResponse:
        """
        Stream a Telegram file directly to the HTTP client.

        Args:
            request:     The incoming aiohttp request (needed for Range header).
            file_hash:   Hashed file identifier stored in MongoDB.
            is_download: True → Content-Disposition: attachment (force download).

        Returns:
            aiohttp StreamResponse (headers already sent, body written).
        """
        # ── 1. Resolve file from DB ──────────────────────────────────────
        file_data = await self.db.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="File not found")

        # ── 2. Bandwidth guard ───────────────────────────────────────────
        stats = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="Bandwidth limit exceeded")

        # ── 3. Fetch Telegram message ────────────────────────────────────
        message = await self.bot.get_messages(
            Config.DUMP_CHAT_ID, int(file_data["message_id"])
        )
        if not message or message.empty:
            raise web.HTTPNotFound(reason="File not found in channel")

        # ── 4. Extract media object ──────────────────────────────────────
        media = (
            message.document
            or message.video
            or message.audio
            or message.photo
        )
        if not media:
            raise web.HTTPBadRequest(reason="Unsupported file type")

        file_size = file_data["file_size"]
        file_name = file_data["file_name"]

        # ── 5. Range negotiation ─────────────────────────────────────────
        range_data = _parse_range(request.headers.get("Range", ""), file_size)
        if range_data:
            start, end   = range_data
            status       = 206
            content_len  = end - start + 1
        else:
            start, end   = 0, file_size - 1
            status       = 200
            content_len  = file_size

        # ── 6. MIME type ─────────────────────────────────────────────────
        mime = (
            file_data.get("mime_type")
            or Config.MIME_TYPE_MAP.get(file_data.get("file_type"), "application/octet-stream")
        )

        # ── 7. Build StreamResponse ──────────────────────────────────────
        disposition = "attachment" if is_download else "inline"
        response = web.StreamResponse(
            status=status,
            headers={
                "Content-Type":        mime,
                "Content-Length":      str(content_len),
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Accept-Ranges":       "bytes",
                "Cache-Control":       Config.CACHE_CONTROL_PUBLIC,
                "Access-Control-Allow-Origin": "*",
            },
        )
        if status == 206:
            response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        await response.prepare(request)

        # ── 8. Stream chunks from Telegram ──────────────────────────────
        bytes_sent = 0
        try:
            async for chunk in self.bot.stream_media(
                message, offset=start, limit=content_len
            ):
                if not chunk:
                    continue
                remaining = content_len - bytes_sent
                to_write  = chunk[:remaining]
                await response.write(to_write)
                bytes_sent += len(to_write)
                if bytes_sent >= content_len:
                    break
        except asyncio.CancelledError:
            logger.warning(f"Stream cancelled for {file_hash}")
        except Exception as exc:
            logger.error(f"Streaming error for {file_hash}: {exc}", exc_info=True)
        finally:
            await response.write_eof()

        # ── 9. Async bookkeeping ─────────────────────────────────────────
        asyncio.create_task(
            self.db.increment_downloads(file_data["message_id"], bytes_sent)
        )

        return response
