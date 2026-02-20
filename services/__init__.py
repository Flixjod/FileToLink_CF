"""
File Streaming Service
──────────────────────
Implements proper HTTP range-request streaming via Pyrogram's stream_media.
Uses the same chunk-aligned offset / cut logic as the reference media_streamer
so seeking, partial downloads and browser players all work correctly.
"""
import math
import mimetypes
import asyncio
import logging
from typing import Optional, Tuple, AsyncGenerator

from aiohttp import web
from pyrogram import Client

from database import Database
from config import Config
from utils import format_size

logger = logging.getLogger(__name__)

# ── Chunk size used for all streaming (1 MiB — matches reference impl) ─────
CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _parse_range(
    range_header: str,
    file_size: int,
) -> Tuple[int, int]:
    """
    Parse an HTTP Range header and return (from_bytes, until_bytes).
    Falls back to the full file when no Range header is present.
    """
    if range_header:
        try:
            raw = range_header.replace("bytes=", "")
            start_str, end_str = raw.split("-")
            from_bytes  = int(start_str)
            until_bytes = int(end_str) if end_str else file_size - 1
        except (ValueError, AttributeError):
            from_bytes  = 0
            until_bytes = file_size - 1
    else:
        from_bytes  = 0
        until_bytes = file_size - 1

    return from_bytes, until_bytes


def _get_file_name(media) -> str:
    """Extract filename from a Pyrogram media object."""
    return (
        getattr(media, "file_name", None)
        or getattr(media, "file_unique_id", "file")
    )


class StreamingService:
    """
    Handle file streaming with range-request support.
    Mirrors the reference media_streamer logic:
      - chunk-aligned offset
      - first_part_cut / last_part_cut trimming
      - part_count based iteration
    """

    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db  = db

    # ── Public entry points ────────────────────────────────────────────────

    async def stream_file(
        self,
        request:     web.Request,
        file_hash:   str,
        is_download: bool = False,
    ) -> web.Response:
        """
        Stream a Telegram file to the HTTP client with full range-request support.

        Routes
        ------
        /stream/<file_hash>  →  is_download=False  (inline / player)
        /dl/<file_hash>      →  is_download=True   (attachment / force-download)
        """
        # ── 1. Resolve file record ────────────────────────────────────────
        file_data = await self.db.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ")

        # ── 2. Bandwidth guard ────────────────────────────────────────────
        stats  = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ")

        # ── 3. Fetch the Telegram message ─────────────────────────────────
        message = await self.bot.get_messages(
            Config.DUMP_CHAT_ID, int(file_data["message_id"])
        )
        if not message or message.empty:
            raise web.HTTPNotFound(reason="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴄʜᴀɴɴᴇʟ")

        # ── 4. Extract media object ────────────────────────────────────────
        media = (
            message.document
            or message.video
            or message.audio
            or message.photo
        )
        if not media:
            raise web.HTTPBadRequest(reason="ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ")

        file_size = file_data["file_size"]
        file_name = file_data["file_name"]

        # ── 5. Range negotiation ──────────────────────────────────────────
        range_header = request.headers.get("Range", "")
        from_bytes, until_bytes = _parse_range(range_header, file_size)

        # Validate range
        if (
            until_bytes > file_size - 1
            or from_bytes < 0
            or until_bytes < from_bytes
        ):
            return web.Response(
                status=416,
                body="416: Range Not Satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        # Clamp
        until_bytes = min(until_bytes, file_size - 1)
        req_length  = until_bytes - from_bytes + 1

        # ── 6. Chunk-aligned offsets (mirrors reference impl) ─────────────
        offset         = from_bytes - (from_bytes % CHUNK_SIZE)
        first_part_cut = from_bytes - offset
        last_part_cut  = until_bytes % CHUNK_SIZE + 1
        part_count     = (
            math.ceil(until_bytes / CHUNK_SIZE)
            - math.floor(offset   / CHUNK_SIZE)
        )

        logger.debug(
            "stream_file | hash=%s from=%d until=%d offset=%d "
            "first_cut=%d last_cut=%d parts=%d",
            file_hash, from_bytes, until_bytes,
            offset, first_part_cut, last_part_cut, part_count,
        )

        # ── 7. MIME type ──────────────────────────────────────────────────
        mime = (
            file_data.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or Config.MIME_TYPE_MAP.get(
                file_data.get("file_type"), "application/octet-stream"
            )
        )

        # ── 8. Content-Disposition ────────────────────────────────────────
        disposition = "attachment" if is_download else "inline"

        # ── 9. Build streaming body ───────────────────────────────────────
        body = self._yield_file(
            message,
            offset,
            first_part_cut,
            last_part_cut,
            part_count,
        )

        # ── 10. Return response ───────────────────────────────────────────
        status = 206 if range_header else 200
        response = web.Response(
            status=status,
            body=body,
            headers={
                "Content-Type":        mime,
                "Content-Range":       f"bytes {from_bytes}-{until_bytes}/{file_size}",
                "Content-Length":      str(req_length),
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Accept-Ranges":       "bytes",
                "Cache-Control":       Config.CACHE_CONTROL_PUBLIC,
                "Access-Control-Allow-Origin": "*",
            },
        )

        # ── 11. Async bookkeeping ─────────────────────────────────────────
        asyncio.create_task(
            self.db.increment_downloads(file_data["message_id"], req_length)
        )

        return response

    # ── Internal generator ─────────────────────────────────────────────────

    async def _yield_file(
        self,
        message,
        offset:         int,
        first_part_cut: int,
        last_part_cut:  int,
        part_count:     int,
    ) -> AsyncGenerator[bytes, None]:
        """
        Yield exactly the requested byte range from Telegram.

        • The first chunk is sliced from first_part_cut onward.
        • The last  chunk is sliced up to last_part_cut.
        • Middle chunks are yielded whole.
        """
        current_part = 1
        try:
            async for chunk in self.bot.stream_media(message, offset=offset):
                if not chunk:
                    continue

                if part_count == 1:
                    # Single-chunk request: apply both cuts
                    yield chunk[first_part_cut:last_part_cut]

                elif current_part == 1:
                    # First chunk: trim the head
                    yield chunk[first_part_cut:]

                elif current_part == part_count:
                    # Last chunk: trim the tail
                    yield chunk[:last_part_cut]

                else:
                    # Middle chunks: pass through whole
                    yield chunk

                current_part += 1
                if current_part > part_count:
                    break

        except asyncio.CancelledError:
            logger.warning("Stream cancelled mid-transfer")
        except Exception as exc:
            logger.error("Streaming error: %s", exc, exc_info=True)
