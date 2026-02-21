import asyncio
import logging
import math
import mimetypes
from typing import Dict, Union

from aiohttp import web
from pyrogram import Client, utils, raw
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Auth, Session

from config import Config
from database import Database

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB

MIME_TYPE_MAP = {
    "video":    "video/mp4",
    "audio":    "audio/mpeg",
    "image":    "image/jpeg",
    "document": "application/octet-stream",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def get_file_ids(client: Client, message_id: str) -> FileId:
    """
    Fetches the Pyrogram Message for *message_id* from DUMP_CHAT_ID and
    returns the unpacked FileId for the attached media.
    """
    msg = await client.get_messages(Config.DUMP_CHAT_ID, int(message_id))
    if not msg or msg.empty:
        raise ValueError(f"message {message_id} not found in dump chat")

    media = (
        msg.document
        or msg.video
        or msg.audio
        or msg.photo
        or msg.sticker
        or msg.animation
        or msg.voice
        or msg.video_note
    )
    if not media:
        raise ValueError(f"message {message_id} contains no streamable media")

    return FileId.decode(media.file_id)


# ---------------------------------------------------------------------------
# ByteStreamer
# ---------------------------------------------------------------------------

class ByteStreamer:
    """
    Low-level Telegram media streamer.

    Mirrors the classic megadlbot / FileStreamBot ByteStreamer pattern:
    - caches decoded FileId objects to avoid repeat API calls
    - manages per-DC media sessions with proper auth export/import
    - yields raw bytes via the MTProto upload.GetFile RPC
    """

    def __init__(self, client: Client):
        self.client: Client = client
        self.cached_file_ids: Dict[str, FileId] = {}
        self.clean_timer: int = 30 * 60           # seconds
        asyncio.create_task(self.clean_cache())

    # ------------------------------------------------------------------
    # FileId cache
    # ------------------------------------------------------------------

    async def get_file_properties(self, db_id: str) -> FileId:
        """
        Return a cached (or freshly generated) FileId for *db_id*
        (which is the string message_id stored in the database).
        """
        if db_id not in self.cached_file_ids:
            logger.debug("FileId cache miss for %s — fetching from Telegram", db_id)
            await self.generate_file_properties(db_id)
            logger.debug("Cached FileId for message %s", db_id)
        return self.cached_file_ids[db_id]

    async def generate_file_properties(self, db_id: str) -> FileId:
        """Decode the FileId from the Telegram message and store it in cache."""
        file_id = await get_file_ids(self.client, db_id)
        logger.debug("Decoded FileId for message %s  dc=%s", db_id, file_id.dc_id)
        self.cached_file_ids[db_id] = file_id
        return file_id

    # ------------------------------------------------------------------
    # DC media session management
    # ------------------------------------------------------------------

    async def generate_media_session(self, client: Client, file_id: FileId) -> Session:
        """
        Return (and cache) a Pyrogram Session for the DC that owns the file.
        Creates a new authorised session when necessary.
        """
        media_session = client.media_sessions.get(file_id.dc_id)

        if media_session is None:
            if file_id.dc_id != await client.storage.dc_id():
                # Foreign DC — need to export + import authorization
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await Auth(
                        client,
                        file_id.dc_id,
                        await client.storage.test_mode(),
                    ).create(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

                for _ in range(6):
                    exported_auth = await client.invoke(
                        raw.functions.auth.ExportAuthorization(dc_id=file_id.dc_id)
                    )
                    try:
                        await media_session.invoke(
                            raw.functions.auth.ImportAuthorization(
                                id=exported_auth.id,
                                bytes=exported_auth.bytes,
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        logger.debug("Invalid auth bytes for DC %s — retrying", file_id.dc_id)
                        continue
                else:
                    await media_session.stop()
                    raise AuthBytesInvalid

            else:
                # Same DC — reuse the existing auth key
                media_session = Session(
                    client,
                    file_id.dc_id,
                    await client.storage.auth_key(),
                    await client.storage.test_mode(),
                    is_media=True,
                )
                await media_session.start()

            logger.debug("Created media session for DC %s", file_id.dc_id)
            client.media_sessions[file_id.dc_id] = media_session

        else:
            logger.debug("Reusing cached media session for DC %s", file_id.dc_id)

        return media_session

    # ------------------------------------------------------------------
    # InputFileLocation builder
    # ------------------------------------------------------------------

    @staticmethod
    async def get_location(
        file_id: FileId,
    ) -> Union[
        raw.types.InputPhotoFileLocation,
        raw.types.InputDocumentFileLocation,
        raw.types.InputPeerPhotoFileLocation,
    ]:
        """Build the correct InputFileLocation for the given FileId."""
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id,
                    access_hash=file_id.chat_access_hash,
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash,
                    )
            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )

        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )

        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )

        return location

    # ------------------------------------------------------------------
    # Core byte generator
    # ------------------------------------------------------------------

    async def yield_file(
        self,
        file_id: FileId,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ):
        """
        Async generator that yields the requested byte range of a
        Telegram media file directly via MTProto upload.GetFile.

        Adapted from:
        https://github.com/eyaadh/megadlbot_oss/blob/master/mega/telegram/utils/custom_download.py
        Thanks to Eyaadh (https://github.com/eyaadh).
        """
        client = self.client
        media_session = await self.generate_media_session(client, file_id)
        location = await self.get_location(file_id)
        current_part = 1

        try:
            r = await media_session.invoke(
                raw.functions.upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=chunk_size,
                )
            )

            if isinstance(r, raw.types.upload.File):
                while True:
                    chunk = r.bytes
                    if not chunk:
                        break

                    if part_count == 1:
                        yield chunk[first_part_cut:last_part_cut]
                    elif current_part == 1:
                        yield chunk[first_part_cut:]
                    elif current_part == part_count:
                        yield chunk[:last_part_cut]
                    else:
                        yield chunk

                    current_part += 1
                    offset += chunk_size

                    if current_part > part_count:
                        break

                    r = await media_session.invoke(
                        raw.functions.upload.GetFile(
                            location=location,
                            offset=offset,
                            limit=chunk_size,
                        )
                    )

        except (TimeoutError, AttributeError):
            pass
        finally:
            logger.debug("yield_file finished after %d part(s)", current_part - 1)

    # ------------------------------------------------------------------
    # Cache janitor
    # ------------------------------------------------------------------

    async def clean_cache(self) -> None:
        """Periodically evict all cached FileIds to free memory."""
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            logger.debug("ByteStreamer cache cleared")


# ---------------------------------------------------------------------------
# Range-request helper
# ---------------------------------------------------------------------------

def _parse_range(range_header: str, file_size: int):
    if range_header:
        try:
            raw_range  = range_header.replace("bytes=", "")
            start_str, end_str = raw_range.split("-")
            from_bytes  = int(start_str)
            until_bytes = int(end_str) if end_str else file_size - 1
        except (ValueError, AttributeError):
            from_bytes  = 0
            until_bytes = file_size - 1
    else:
        from_bytes  = 0
        until_bytes = file_size - 1
    return from_bytes, until_bytes


# ---------------------------------------------------------------------------
# High-level aiohttp streaming service
# ---------------------------------------------------------------------------

class StreamingService:
    """
    aiohttp request handler that sits on top of ByteStreamer.
    One ByteStreamer instance is kept for the lifetime of the service.
    """

    def __init__(self, bot_client: Client, db: Database):
        self.bot      = bot_client
        self.db       = db
        self.streamer = ByteStreamer(bot_client)

    async def stream_file(
        self,
        request: web.Request,
        file_hash: str,
        is_download: bool = False,
    ) -> web.StreamResponse:

        # ── Resolve file record ──────────────────────────────────────
        file_data = await self.db.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="file not found")

        # ── Bandwidth guard ──────────────────────────────────────────
        stats  = await self.db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            raise web.HTTPServiceUnavailable(reason="bandwidth limit exceeded")

        file_size = file_data["file_size"]
        file_name = file_data["file_name"]
        message_id = str(file_data["message_id"])

        # ── Range parsing ─────────────────────────────────────────────
        range_header               = request.headers.get("Range", "")
        from_bytes, until_bytes    = _parse_range(range_header, file_size)

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

        # ── MIME / headers ───────────────────────────────────────────
        mime = (
            file_data.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or MIME_TYPE_MAP.get(file_data.get("file_type"), "application/octet-stream")
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

        # ── Fetch FileId (cached) and stream bytes ───────────────────
        try:
            file_id = await self.streamer.get_file_properties(message_id)
        except Exception as exc:
            logger.error("get_file_properties failed: msg=%s err=%s", message_id, exc)
            raise web.HTTPNotFound(reason="could not resolve file on Telegram")

        async for chunk in self.streamer.yield_file(
            file_id,
            offset,
            first_part_cut,
            last_part_cut,
            part_count,
            CHUNK_SIZE,
        ):
            await response.write(chunk)

        await response.write_eof()

        # ── Track stats asynchronously ───────────────────────────────
        asyncio.create_task(
            self.db.increment_downloads(message_id, req_length)
        )

        return response
