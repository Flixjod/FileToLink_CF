import math
import mimetypes
import asyncio
import logging
from typing import Tuple, AsyncGenerator

from aiohttp import web
from pyrogram import Client

from database import Database
from config import Config

logger = logging.getLogger(__name__)

# Pyrogram streams in 1 MiB chunks — never change this
CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _parse_range(range_header: str, file_size: int) -> Tuple[int, int]:
    """Parse HTTP Range header → (from_bytes, until_bytes). Full file on miss."""
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


class StreamingService:
    """Chunk-aligned HTTP range streaming via Pyrogram stream_media."""

    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db  = db

    async def stream_file(
        self,
        request:     web.Request,
        file_hash:   str,
        is_download: bool = False,
    ) -> web.StreamResponse:

        # 1 — resolve file record
        file_data = await self.db.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ")

        # 2 — bandwidth guard
        stats  = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ")

        # 3 — fetch Telegram message
        message = await self.bot.get_messages(
            Config.DUMP_CHAT_ID, int(file_data["message_id"])
        )
        if not message or message.empty:
            raise web.HTTPNotFound(reason="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴄʜᴀɴɴᴇʟ")

        # 4 — extract media object
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

        # 5 — range negotiation
        range_header = request.headers.get("Range", "")
        from_bytes, until_bytes = _parse_range(range_header, file_size)

        # validate
        if (
            until_bytes > file_size - 1
            or from_bytes < 0
            or until_bytes < from_bytes
        ):
            raise web.HTTPRequestRangeNotSatisfiable(
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        until_bytes = min(until_bytes, file_size - 1)
        req_length  = until_bytes - from_bytes + 1

        # 6 — chunk-aligned offsets
        offset         = from_bytes - (from_bytes % CHUNK_SIZE)
        first_part_cut = from_bytes - offset
        last_part_cut  = until_bytes % CHUNK_SIZE + 1
        part_count     = (
            math.ceil(until_bytes / CHUNK_SIZE)
            - math.floor(offset   / CHUNK_SIZE)
        )

        logger.debug(
            "stream | hash=%s from=%d until=%d offset=%d cuts=%d/%d parts=%d",
            file_hash, from_bytes, until_bytes,
            offset, first_part_cut, last_part_cut, part_count,
        )

        # 7 — MIME
        mime = (
            file_data.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or Config.MIME_TYPE_MAP.get(
                file_data.get("file_type"), "application/octet-stream"
            )
        )

        # 8 — disposition
        disposition = "attachment" if is_download else "inline"

        # 9 — StreamResponse (NOT web.Response) for chunked delivery
        #     This is critical: web.Response buffers the full body before sending,
        #     which breaks VLC, MX Player and browser seeking.
        #     web.StreamResponse flushes each chunk immediately.
        status = 206 if range_header else 200
        response = web.StreamResponse(
            status=status,
            headers={
                "Content-Type":        mime,
                "Content-Range":       f"bytes {from_bytes}-{until_bytes}/{file_size}",
                "Content-Length":      str(req_length),
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Accept-Ranges":       "bytes",
                "Cache-Control":       "no-cache",
                "Connection":          "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )

        await response.prepare(request)

        # 10 — stream chunks to client
        await self._pipe_chunks(
            response, message,
            offset, first_part_cut, last_part_cut, part_count,
        )

        await response.write_eof()

        # 11 — async bookkeeping (fire-and-forget)
        asyncio.create_task(
            self.db.increment_downloads(file_data["message_id"], req_length)
        )

        return response

    # ── Internal chunk pipeline ────────────────────────────────────────────

    async def _pipe_chunks(
        self,
        response:       web.StreamResponse,
        message,
        offset:         int,
        first_part_cut: int,
        last_part_cut:  int,
        part_count:     int,
    ) -> None:
        """Write exactly the requested byte range to the StreamResponse."""
        current_part = 1
        try:
            async for chunk in self.bot.stream_media(message, offset=offset):
                if not chunk:
                    continue

                if part_count == 1:
                    await response.write(chunk[first_part_cut:last_part_cut])
                elif current_part == 1:
                    await response.write(chunk[first_part_cut:])
                elif current_part == part_count:
                    await response.write(chunk[:last_part_cut])
                else:
                    await response.write(chunk)

                current_part += 1
                if current_part > part_count:
                    break

        except asyncio.CancelledError:
            logger.warning("stream cancelled mid-transfer hash=%s", id(message))
        except ConnectionResetError:
            logger.debug("client disconnected during stream")
        except Exception as exc:
            logger.error("stream error: %s", exc, exc_info=True)
