import math
import mimetypes
import asyncio
import logging

from aiohttp import web
from pyrogram import Client

from database import Database
from config import Config

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024


def _parse_range(range_header: str, file_size: int):
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


async def _yield_file(bot, message, offset, first_part_cut, last_part_cut, part_count):
    current_part = 1
    try:
        async for chunk in bot.stream_media(message, offset=offset):
            if not chunk:
                continue

            if part_count == 1:
                yield chunk[first_part_cut:last_part_cut]
            elif current_part == 1:
                yield chunk[first_part_cut:]
            elif current_part == part_count:
                yield chunk[:last_part_cut]
            else:
                yield chunk

            current_part += 1
            if current_part > part_count:
                break

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("stream error: %s", exc)


class StreamingService:

    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db  = db

    async def stream_file(self, request: web.Request, file_hash: str, is_download: bool = False) -> web.StreamResponse:
        file_data = await self.db.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="file not found")

        stats  = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="bandwidth limit exceeded")

        message = await self.bot.get_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
        if not message or message.empty:
            raise web.HTTPNotFound(reason="file not found in channel")

        media = (
            message.document
            or message.video
            or message.audio
            or message.photo
        )
        if not media:
            raise web.HTTPBadRequest(reason="unsupported media type")

        file_size = file_data["file_size"]
        file_name = file_data["file_name"]

        range_header = request.headers.get("Range", "")
        from_bytes, until_bytes = _parse_range(range_header, file_size)

        if until_bytes > file_size - 1 or from_bytes < 0 or until_bytes < from_bytes:
            return web.Response(
                status=416,
                body=b"Range Not Satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        until_bytes = min(until_bytes, file_size - 1)
        req_length  = until_bytes - from_bytes + 1

        offset         = from_bytes - (from_bytes % CHUNK_SIZE)
        first_part_cut = from_bytes - offset
        last_part_cut  = until_bytes % CHUNK_SIZE + 1
        part_count     = (
            math.ceil(until_bytes / CHUNK_SIZE)
            - math.floor(offset   / CHUNK_SIZE)
        )

        mime = (
            file_data.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or Config.MIME_TYPE_MAP.get(file_data.get("file_type"), "application/octet-stream")
        )

        disposition = "attachment" if is_download else "inline"
        status      = 206 if range_header else 200

        response = web.StreamResponse(
            status=status,
            headers={
                "Content-Type":        mime,
                "Content-Range":       f"bytes {from_bytes}-{until_bytes}/{file_size}",
                "Content-Length":      str(req_length),
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Accept-Ranges":       "bytes",
                "Cache-Control":       "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "Connection":          "keep-alive",
            },
        )

        await response.prepare(request)

        async for chunk in _yield_file(self.bot, message, offset, first_part_cut, last_part_cut, part_count):
            await response.write(chunk)

        await response.write_eof()

        asyncio.create_task(
            self.db.increment_downloads(file_data["message_id"], req_length)
        )

        return response
