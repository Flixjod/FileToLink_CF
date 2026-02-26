import json
import logging
from pathlib import Path

from aiohttp import web
import aiohttp_jinja2
import jinja2

from bot import Bot
from config import Config
from database import Database
from helper import StreamingService, check_bandwidth_limit, format_size

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def build_app(bot: Bot, database) -> web.Application:
    streaming_service = StreamingService(bot, database)

    @web.middleware
    async def not_found_middleware(request: web.Request, handler):
        try:
            return await handler(request)
        except web.HTTPNotFound:
            return await _render_not_found(request)
        except web.HTTPServiceUnavailable:
            return await _render_bandwidth_exceeded(request)

    async def _render_not_found(request: web.Request) -> web.Response:
        try:
            return aiohttp_jinja2.render_template(
                "not_found.html",
                request,
                {
                    "bot_name":     Config.BOT_NAME     or Config.DEFAULT_BOT_NAME,
                    "bot_username": Config.BOT_USERNAME or Config.DEFAULT_BOT_USERNAME,
                },
            )
        except Exception as exc:
            logger.error("not_found template error: %s", exc)
            return web.Response(status=404, text="404 — File not found", content_type="text/plain")

    async def _render_bandwidth_exceeded(request: web.Request) -> web.Response:
        try:
            return aiohttp_jinja2.render_template(
                "bandwidth_exceeded.html",
                request,
                {
                    "bot_name":       Config.BOT_NAME,
                    "bot_username":   Config.BOT_USERNAME,
                    "owner_username": "FLiX_LY",
                },
            )
        except Exception as exc:
            logger.error("bandwidth_exceeded template error: %s", exc)
            return web.Response(
                status=503,
                text="Bandwidth limit exceeded",
                content_type="text/plain",
            )

    app = web.Application(middlewares=[not_found_middleware])
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))

    @aiohttp_jinja2.template("home.html")
    async def home(request: web.Request):
        return {
            "bot_name":       Config.BOT_NAME,
            "bot_username":   Config.BOT_USERNAME,
            "owner_username": "FLiX_LY",
        }

    async def stream_page(request: web.Request):
        """
        GET /stream/<file_hash>

        - Browser requests (Accept: text/html, no Range) → render HTML player page.
        - Media player / Range requests                  → stream bytes directly.
        """
        file_hash = request.match_info["file_hash"]
        accept    = request.headers.get("Accept", "")
        range_h   = request.headers.get("Range", "")

        # ── Direct byte streaming for media players & range requests ──────
        if range_h or "text/html" not in accept:
            return await streaming_service.stream_file(
                request, file_hash, is_download=False
            )

        # ── HTML player page for browsers ──────────────────────────────────
        file_data = await database.get_file_by_hash(file_hash)
        if not file_data:
            raise web.HTTPNotFound(reason="File not found")

        allowed, _ = await check_bandwidth_limit(database)
        if not allowed:
            raise web.HTTPServiceUnavailable(reason="bandwidth limit exceeded")

        base      = str(request.url.origin())
        file_type = (
            "video"   if file_data["file_type"] == Config.FILE_TYPE_VIDEO
            else "audio" if file_data["file_type"] == Config.FILE_TYPE_AUDIO
            else "document"
        )

        context = {
            "bot_name":       Config.BOT_NAME,
            "bot_username":   Config.BOT_USERNAME,
            "owner_username": "FLiX_LY",
            "file_name":      file_data["file_name"],
            "file_size":      format_size(file_data["file_size"]),
            "file_type":      file_type,
            "stream_url":     f"{base}/stream/{file_hash}",
            "download_url":   f"{base}/dl/{file_hash}",
            "telegram_url":   f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}",
        }
        return aiohttp_jinja2.render_template("stream.html", request, context)

    async def download_file(request: web.Request):
        """GET /dl/<file_hash> — always force-download."""
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
            stats  = await database.get_bandwidth_stats()
            max_bw = Config.get("max_bandwidth", 107374182400)
            used   = stats["total_bandwidth"]
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
