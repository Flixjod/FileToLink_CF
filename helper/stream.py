import math
import mimetypes
import asyncio
import logging

from aiohttp import web
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError

from database import Database
from config import Config

logger = logging.getLogger(__name__)

# 1 MiB chunks — matches Telegram's internal part size
CHUNK_SIZE = 1024 * 1024


def _parse_range(range_header: str, file_size: int):
    """
    Parse an HTTP Range header and return (from_bytes, until_bytes).
    Falls back to full-file range on any parse error.
    """
    if range_header:
        try:
            raw = range_header.strip().replace("bytes=", "")
            start_str, end_str = raw.split("-", 1)
            from_bytes  = int(start_str) if start_str else 0
            until_bytes = int(end_str)   if end_str   else file_size - 1
        except (ValueError, AttributeError):
            from_bytes  = 0
            until_bytes = file_size - 1
    else:
        from_bytes  = 0
        until_bytes = file_size - 1

    return from_bytes, until_bytes


async def _yield_file(bot, message, offset, first_part_cut, last_part_cut, part_count):
    """
    Yield raw bytes from a Telegram media message for the requested byte range.

    Telegram streams in CHUNK_SIZE (1 MiB) parts.  We slice the first and last
    part to honour the exact Range the client asked for.
    """
    current_part = 1
    try:
        async for chunk in bot.stream_media(message, offset=offset):
            if not chunk:
                continue

            if part_count == 1:
                # Both first and last part — apply both cuts
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
        # Client disconnected — normal, not an error
        pass
    except FloodWait as fw:
        logger.warning("stream FloodWait %ss", fw.value)
        await asyncio.sleep(fw.value)
    except Exception as exc:
        logger.error("stream error: %s", exc)


async def _resolve_file_data(db: Database, bot, file_hash: str):
    """
    Step 1 — look up file metadata in the database.
    Step 2 — if not found, fetch the message from Telegram, extract metadata,
              save to database, and return it.
    Step 3 — if Telegram also has nothing, return None.

    Returns (file_data_dict, message_object) or (None, None).
    """
    # ── Step 1: database cache ────────────────────────────────────────────
    file_data = await db.get_file_by_hash(file_hash)
    if file_data:
        # We still need the Pyrogram message object to stream bytes
        try:
            message = await bot.get_messages(
                Config.DUMP_CHAT_ID, int(file_data["message_id"])
            )
            if message and not message.empty:
                return file_data, message
            # Message gone from Telegram — fall through to Step 3
            logger.warning(
                "message %s not found on Telegram (db record exists)",
                file_data["message_id"],
            )
        except RPCError as exc:
            logger.error("get_messages RPC error: %s", exc)
        return None, None

    # ── Step 2: Telegram fallback ─────────────────────────────────────────
    # file_hash is derived from message_id via Cryptic.hash_file_id — we
    # cannot reverse it here without iterating, so we can only return 404
    # when the db record is truly absent.  (If you store message_id in the
    # hash URL directly, swap to that lookup.)
    logger.info("file_hash %s not in database — no Telegram fallback possible without message_id", file_hash)

    # ── Step 3: not found ─────────────────────────────────────────────────
    return None, None


async def _resolve_file_data_by_message_id(db: Database, bot, message_id: str):
    """
    Alternative resolver that accepts a plain message_id.
    Used internally when we already know the message_id but the db record is
    missing (e.g. the file was sent before the bot tracked it).
    Fetches from Telegram, saves metadata, returns (file_data, message).
    """
    # ── Step 1: database cache ────────────────────────────────────────────
    file_data = await db.get_file(message_id)
    if file_data:
        try:
            message = await bot.get_messages(Config.DUMP_CHAT_ID, int(message_id))
            if message and not message.empty:
                return file_data, message
        except RPCError as exc:
            logger.error("get_messages RPC error: %s", exc)
        return None, None

    # ── Step 2: fetch from Telegram and cache ─────────────────────────────
    try:
        message = await bot.get_messages(Config.DUMP_CHAT_ID, int(message_id))
    except RPCError as exc:
        logger.error("Telegram fallback get_messages failed: %s", exc)
        return None, None

    if not message or message.empty:
        return None, None

    media = (
        message.document
        or message.video
        or message.audio
        or message.photo
    )
    if not media:
        return None, None

    # Determine file metadata from Pyrogram media object
    from helper.crypto import Cryptic  # lazy import to avoid circularity

    file_type = "document"
    if message.video:
        file_type = "video"
    elif message.audio:
        file_type = "audio"
    elif message.photo:
        file_type = "image"
    elif message.document and message.document.mime_type:
        mime_root = message.document.mime_type.split("/")[0]
        if mime_root in ("video", "audio", "image"):
            file_type = mime_root

    file_name = (
        getattr(media, "file_name", None)
        or (f"{media.file_unique_id}.jpg" if message.photo else None)
        or "Unknown"
    )
    file_size = getattr(media, "file_size", 0) or 0
    mime_type = getattr(media, "mime_type", "") or ""
    file_hash = Cryptic.hash_file_id(message_id)

    doc = {
        "file_id":          file_hash,
        "message_id":       message_id,
        "telegram_file_id": getattr(media, "file_id", ""),
        "user_id":          "unknown",
        "username":         "",
        "file_name":        file_name,
        "file_size":        file_size,
        "file_type":        file_type,
        "mime_type":        mime_type,
    }
    await db.add_file(doc)
    logger.info(
        "Telegram fallback: cached new file %s (msg_id=%s)", file_hash, message_id
    )
    return doc, message


class StreamingService:

    def __init__(self, bot_client: Client, db: Database):
        self.bot = bot_client
        self.db  = db

    # ------------------------------------------------------------------ #
    #  Public entry-point called by both /stream/<hash> and /dl/<hash>    #
    # ------------------------------------------------------------------ #
    async def stream_file(
        self,
        request: web.Request,
        file_hash: str,
        is_download: bool = False,
    ) -> web.StreamResponse:
        """
        Resolve file metadata (cache → Telegram fallback → 404),
        then stream the requested byte range back to the client.
        """

        # ── 1. Resolve metadata + Telegram message ─────────────────────
        file_data, message = await _resolve_file_data(self.db, self.bot, file_hash)

        if file_data is None or message is None:
            raise web.HTTPNotFound(reason="File not found")

        # ── 2. Bandwidth guard ──────────────────────────────────────────
        stats  = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="Bandwidth limit exceeded")

        # ── 3. Confirm media exists on the message ──────────────────────
        media = (
            message.document
            or message.video
            or message.audio
            or message.photo
        )
        if not media:
            raise web.HTTPNotFound(reason="Media not found on message")

        # ── 4. Range parsing ────────────────────────────────────────────
        file_size    = file_data["file_size"]
        file_name    = file_data["file_name"]
        range_header = request.headers.get("Range", "")

        from_bytes, until_bytes = _parse_range(range_header, file_size)

        # Clamp to valid bounds
        from_bytes  = max(0, from_bytes)
        until_bytes = min(until_bytes, file_size - 1)

        # Sanity check
        if from_bytes > until_bytes or from_bytes >= file_size:
            return web.Response(
                status=416,
                headers={"Content-Range": f"bytes */{file_size}"},
                body=b"Range Not Satisfiable",
            )

        req_length = until_bytes - from_bytes + 1

        # ── 5. Calculate Telegram streaming offsets ─────────────────────
        #
        # Telegram delivers media in 1 MiB parts starting at an aligned
        # offset.  We ask it to start at the 1 MiB-aligned offset that
        # contains `from_bytes`, then cut the unwanted leading bytes from the
        # first part and trim the last part at `until_bytes`.
        #
        offset         = from_bytes - (from_bytes % CHUNK_SIZE)
        first_part_cut = from_bytes - offset
        last_part_cut  = until_bytes % CHUNK_SIZE + 1
        part_count     = (
            math.ceil((until_bytes + 1) / CHUNK_SIZE)
            - math.floor(offset        / CHUNK_SIZE)
        )

        # ── 6. Determine MIME type ──────────────────────────────────────
        mime = (
            file_data.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or Config.MIME_TYPE_MAP.get(file_data.get("file_type"), "application/octet-stream")
        )

        # ── 7. Build response headers ───────────────────────────────────
        disposition = "attachment" if is_download else "inline"
        status      = 206 if range_header else 200

        # Always include Content-Range so players can seek
        headers = {
            "Content-Type":        mime,
            "Content-Range":       f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length":      str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges":       "bytes",
            "Cache-Control":       "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "Connection":          "keep-alive",
        }

        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)

        # ── 8. Stream bytes progressively ──────────────────────────────
        try:
            async for chunk in _yield_file(
                self.bot, message, offset,
                first_part_cut, last_part_cut, part_count,
            ):
                await response.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            # Client disconnected mid-stream — not an error we can recover
            logger.debug("client disconnected during stream of %s", file_hash)
            return response

        await response.write_eof()

        # ── 9. Async stats update (fire-and-forget) ─────────────────────
        asyncio.create_task(
            self.db.increment_downloads(file_data["message_id"], req_length)
        )

        return response
