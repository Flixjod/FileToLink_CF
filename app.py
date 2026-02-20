"""
aiohttp Web Application
All routes are fully async – no Flask, no threading.

Routes
──────
GET /                         → home page
GET /stream/{file_hash}       → streaming page (FLiX template) AND raw stream
GET /dl/{file_hash}           → force-download
GET /stats                    → JSON statistics
GET /bandwidth                → JSON bandwidth info
GET /health                   → health-check JSON
"""
import json
import logging
from pathlib import Path

from aiohttp import web
import aiohttp_jinja2
import jinja2

from bot import bot
from config import Config
from database import Database
from services import StreamingService
from middlewares import check_bandwidth_limit
from utils import format_size

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def build_app(database: Database) -> web.Application:
    """
    Build and return the aiohttp Application.
    Called once from main.py after the DB is ready.
    """
    streaming_service = StreamingService(bot, database)

    app = web.Application()

    # ── Template engine ──────────────────────────────────────────────────
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    )

    # ── Route handlers ───────────────────────────────────────────────────

    @aiohttp_jinja2.template("home.html")
    async def home(request: web.Request):
        """Home page with bot statistics"""
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
            logger.error("Home page error: %s", exc)
            raise web.HTTPInternalServerError(reason=str(exc))

    @aiohttp_jinja2.template("stream.html")
    async def stream_page(request: web.Request):
        """
        Streaming page — URL: /stream/<file_hash>
        Renders the FLiX player HTML; the actual bytes come from the
        same /stream/<file_hash> endpoint when the browser requests the src.
        """
        file_hash = request.match_info["file_hash"]

        # If this is a plain HTTP request (no Range header) with Accept: text/html
        # we return the player page; otherwise we fall through to stream_file.
        accept = request.headers.get("Accept", "")
        range_h = request.headers.get("Range", "")

        # When Range header is present the browser/player wants raw bytes
        if range_h or "text/html" not in accept:
            return await streaming_service.stream_file(
                request, file_hash, is_download=False
            )

        # ── Render the player page ──────────────────────────────────────
        file_data = await database.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ")

        allowed, _ = await check_bandwidth_limit(database)
        if not allowed:
            raise web.HTTPServiceUnavailable(reason="ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ")

        base = str(request.url.origin())
        file_type = (
            "video"    if file_data["file_type"] == Config.FILE_TYPE_VIDEO
            else "audio" if file_data["file_type"] == Config.FILE_TYPE_AUDIO
            else "document"
        )
        return {
            "bot_name":       "FileStream Bot",
            "owner_username": "FLiX_LY",
            "file_name":      file_data["file_name"],
            "file_size":      format_size(file_data["file_size"]),
            "file_type":      file_type,
            "downloads":      file_data.get("downloads", 0),
            "stream_url":     f"{base}/stream/{file_hash}",
            "download_url":   f"{base}/dl/{file_hash}",
            "telegram_url":   f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}",
        }

    async def stream_file_raw(request: web.Request):
        """
        Raw byte streaming endpoint.
        Serves range-requests from browser players, VLC, MX, wget, etc.
        URL: /stream/<file_hash>  (non-HTML Accept / Range present)
        """
        file_hash = request.match_info["file_hash"]
        return await streaming_service.stream_file(
            request, file_hash, is_download=False
        )

    async def download_file(request: web.Request):
        """Download file (Content-Disposition: attachment)"""
        file_hash = request.match_info["file_hash"]
        return await streaming_service.stream_file(
            request, file_hash, is_download=True
        )

    async def stats_endpoint(request: web.Request):
        """JSON statistics endpoint"""
        try:
            stats = await database.get_stats()
            stats["formatted"] = {
                "total_bandwidth": format_size(stats["total_bandwidth"]),
                "today_bandwidth": format_size(stats["today_bandwidth"]),
            }
            return web.Response(
                text=json.dumps(stats), content_type="application/json"
            )
        except Exception as exc:
            logger.error("Stats error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def bandwidth_endpoint(request: web.Request):
        """JSON bandwidth statistics endpoint"""
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
            return web.Response(
                text=json.dumps(stats), content_type="application/json"
            )
        except Exception as exc:
            logger.error("Bandwidth error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def health(request: web.Request):
        """Health check"""
        return web.json_response({
            "status":            "ok",
            "bot":               "running" if Config.BOT_USERNAME else "initializing",
            "bot_username":      Config.BOT_USERNAME,
            "streaming_service": "ready",
        })

    # ── Register routes ──────────────────────────────────────────────────
    app.router.add_get("/",                   home)
    # /stream/<id>  — serves player HTML for browsers, raw bytes for players
    app.router.add_get("/stream/{file_hash}", stream_page)
    # /dl/<id>      — force-download (attachment)
    app.router.add_get("/dl/{file_hash}",     download_file)
    app.router.add_get("/stats",              stats_endpoint)
    app.router.add_get("/bandwidth",          bandwidth_endpoint)
    app.router.add_get("/health",             health)

    return app
