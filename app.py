import json
import logging
from pathlib import Path

from aiohttp import web
import aiohttp_jinja2
import jinja2

from bot import bot
from config import Config
from database import Database
from helper import StreamingService, check_bandwidth_limit, format_size
from helper.stream import _resolve_file_data_by_message_id

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def build_app(database: Database) -> web.Application:
    streaming_service = StreamingService(bot, database)

    app = web.Application()

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    )

    @aiohttp_jinja2.template("home.html")
    async def home(request: web.Request):
        try:
            stats = await database.get_stats()
            return {
                "bot_name":        "FileStream Bot",
                "bot_username":    Config.BOT_USERNAME or "filestream_bot",
                "owner_username":  "FLiX_LY",
                "total_files":     stats["total_files"],
                "total_users":     stats["total_users"],
                "total_downloads": stats["total_downloads"],
            }
        except Exception as exc:
            logger.error("home page error: %s", exc)
            raise web.HTTPInternalServerError(reason=str(exc))

    @aiohttp_jinja2.template("stream.html")
    async def stream_page(request: web.Request):
        """
        Serve the HTML player page for /stream/<file_hash>.

        File-resolution order:
          1. Check database by file_hash.
          2. If not found, return HTTP 404 (we cannot reverse a hash to a
             message_id without storing it, so Telegram fallback is only
             possible via /stream/<message_id> alias — handled below).
        Range requests and binary data are forwarded to streaming_service.
        """
        file_hash = request.match_info["file_hash"]
        accept    = request.headers.get("Accept", "")
        range_h   = request.headers.get("Range", "")

        # If the client is asking for bytes (range request or non-HTML accept),
        # stream the file directly instead of returning the HTML page.
        if range_h or "text/html" not in accept:
            return await streaming_service.stream_file(request, file_hash, is_download=False)

        # ── Step 1: look up in database ──────────────────────────────────
        file_data = await database.get_file_by_hash(file_hash)

        # ── Step 2: Telegram fallback is not possible here because we only
        #    have file_hash (a HMAC, not reversible to message_id).
        #    Return 404 when the record is truly absent.
        if not file_data:
            raise web.HTTPNotFound(reason="File not found")

        # ── Bandwidth check ──────────────────────────────────────────────
        allowed, _ = await check_bandwidth_limit(database)
        if not allowed:
            raise web.HTTPServiceUnavailable(reason="bandwidth limit exceeded")

        # ── Build template context ───────────────────────────────────────
        base = str(request.url.origin())

        file_type = (
            "video"    if file_data["file_type"] == Config.FILE_TYPE_VIDEO
            else "audio"  if file_data["file_type"] == Config.FILE_TYPE_AUDIO
            else "document"
        )

        return {
            "bot_name":       "FileStream Bot",
            "bot_username":   Config.BOT_USERNAME or "filestream_bot",
            "owner_username": "FLiX_LY",
            "file_name":      file_data["file_name"],
            "file_size":      format_size(file_data["file_size"]),
            "file_type":      file_type,
            "downloads":      file_data.get("downloads", 0),
            "stream_url":     f"{base}/stream/{file_hash}",
            "download_url":   f"{base}/dl/{file_hash}",
            "telegram_url":   f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}",
        }

    async def download_file(request: web.Request):
        """
        /dl/<file_hash> — force-attachment download.

        Uses streaming_service which already implements the full
        cache → Telegram fallback → 404 logic.
        """
        file_hash = request.match_info["file_hash"]
        return await streaming_service.stream_file(request, file_hash, is_download=True)

    async def stats_endpoint(request: web.Request):
        try:
            stats = await database.get_stats()
            stats["formatted"] = {
                "total_bandwidth": format_size(stats["total_bandwidth"]),
                "today_bandwidth": format_size(stats["today_bandwidth"]),
            }
            return web.Response(text=json.dumps(stats), content_type="application/json")
        except Exception as exc:
            logger.error("stats error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def bandwidth_endpoint(request: web.Request):
        try:
            stats   = await database.get_bandwidth_stats()
            max_bw  = Config.get("max_bandwidth", 107374182400)
            used    = stats["total_bandwidth"]
            stats["limit"]      = max_bw
            stats["remaining"]  = max_bw - used
            stats["percentage"] = (used / max_bw * 100) if max_bw else 0
            stats["formatted"]  = {
                "total_bandwidth": format_size(used),
                "today_bandwidth": format_size(stats["today_bandwidth"]),
                "limit":           format_size(max_bw),
                "remaining":       format_size(stats["remaining"]),
            }
            return web.Response(text=json.dumps(stats), content_type="application/json")
        except Exception as exc:
            logger.error("bandwidth error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def health(request: web.Request):
        return web.json_response({
            "status":       "ok",
            "bot":          "running" if Config.BOT_USERNAME else "initializing",
            "bot_username": Config.BOT_USERNAME,
        })

    app.router.add_get("/",                   home)
    app.router.add_get("/stream/{file_hash}", stream_page)
    app.router.add_get("/dl/{file_hash}",     download_file)
    app.router.add_get("/stats",              stats_endpoint)
    app.router.add_get("/bandwidth",          bandwidth_endpoint)
    app.router.add_get("/health",             health)

    return app
