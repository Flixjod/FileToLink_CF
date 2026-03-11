import hashlib
import json
import logging
import os
import secrets
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import bcrypt
import psutil
from aiohttp import web
import aiohttp_jinja2
import jinja2

from bot import Bot
from config import Config
from database import Database
from helper import StreamingService, check_bandwidth_limit, format_size
from helper.stream import (
    get_active_session_count,
    _register_session,
    _unregister_session,
    _get_client_ip,
    _mime_for_filename,
    is_browser_playable,
    MIME_TYPE_MAP,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

DEFAULT_BOT_NAME     = "FLiX Stream"
DEFAULT_BOT_USERNAME = "FLiX_LY"

# ---------------------------------------------------------------------------
# Session store (in-memory; keyed by session token)
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}
_SESSION_LIFETIME = timedelta(hours=2)

# ---------------------------------------------------------------------------
# Login rate-limiter (5 attempts / minute per IP)
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list] = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 60  # seconds

# ---------------------------------------------------------------------------
# CSRF token store (maps token → creation_time)
# ---------------------------------------------------------------------------
_csrf_tokens: dict[str, float] = {}
_CSRF_TOKEN_TTL = 3600


def _bot_info(bot: Bot) -> dict:
    me = getattr(bot, "me", None)
    return {
        "bot_name":     (me.first_name if me else None) or DEFAULT_BOT_NAME,
        "bot_username": (me.username   if me else None) or DEFAULT_BOT_USERNAME,
        "bot_id":       str(me.id)    if me else "N/A",
        "bot_dc":       str(me.dc_id) if me else "N/A",
    }


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _create_session() -> str:
    token = secrets.token_urlsafe(48)
    _sessions[token] = {
        "authenticated": True,
        "created_at": datetime.utcnow().isoformat(),
        "last_active": time.monotonic(),
    }
    return token


def _get_session(request: web.Request) -> dict | None:
    token = request.cookies.get("session_token")
    if not token:
        return None
    sess = _sessions.get(token)
    if not sess:
        return None
    # Inactivity expiry
    if time.monotonic() - sess["last_active"] > _SESSION_LIFETIME.total_seconds():
        _sessions.pop(token, None)
        return None
    sess["last_active"] = time.monotonic()
    return sess


def _destroy_session(request: web.Request) -> None:
    token = request.cookies.get("session_token")
    if token:
        _sessions.pop(token, None)


def _is_authenticated(request: web.Request) -> bool:
    sess = _get_session(request)
    return bool(sess and sess.get("authenticated"))


def _session_expired(request: web.Request) -> bool:
    """Returns True if a session cookie exists but has expired."""
    token = request.cookies.get("session_token")
    if not token:
        return False
    if token not in _sessions:
        return True
    sess = _sessions[token]
    if time.monotonic() - sess["last_active"] > _SESSION_LIFETIME.total_seconds():
        _sessions.pop(token, None)
        return True
    return False


# ---------------------------------------------------------------------------
# CSRF helpers
# ---------------------------------------------------------------------------

def _new_csrf_token() -> str:
    token = secrets.token_urlsafe(32)
    _csrf_tokens[token] = time.monotonic()
    return token


def _validate_csrf(token: str | None) -> bool:
    if not token:
        return False
    created = _csrf_tokens.pop(token, None)
    if created is None:
        return False
    if time.monotonic() - created > _CSRF_TOKEN_TTL:
        return False
    return True


def _prune_csrf_tokens() -> None:
    now = time.monotonic()
    expired = [t for t, ts in _csrf_tokens.items() if now - ts > _CSRF_TOKEN_TTL]
    for t in expired:
        del _csrf_tokens[t]


# ---------------------------------------------------------------------------
# Rate-limiter helpers
# ---------------------------------------------------------------------------

def _check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is within the rate limit (allowed), False if exceeded."""
    now = time.monotonic()
    attempts = _login_attempts[ip]
    # Prune old attempts
    _login_attempts[ip] = [ts for ts in attempts if now - ts < _RATE_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_LIMIT:
        return False
    _login_attempts[ip].append(now)
    return True


# ---------------------------------------------------------------------------
# Password verification
# ---------------------------------------------------------------------------

def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    response = await handler(request)
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"]        = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://fonts.gstatic.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https://i.ibb.co https://telegra.ph; "
        "media-src 'self' blob:; "
        "connect-src 'self';"
    )
    return response


def build_app(bot: Bot, database) -> web.Application:
    streaming_service = StreamingService(bot, database)

    @web.middleware
    async def not_found_middleware(request: web.Request, handler):
        try:
            return await handler(request)
        except web.HTTPNotFound:
            if request.headers.get("Accept", "").find("text/html") != -1:
                return web.HTTPFound("/not_found.html")
            return await _render_not_found(request)
        except web.HTTPServiceUnavailable:
            return await _render_bandwidth_exceeded(request)

    async def _render_not_found(request: web.Request) -> web.Response:
        try:
            info = _bot_info(bot)
            return aiohttp_jinja2.render_template(
                "not_found.html",
                request,
                {"bot_name": info["bot_name"], "bot_username": info["bot_username"]},
            )
        except Exception as exc:
            logger.error("not_found template error: %s", exc)
            return web.Response(status=404, text="404 — File not found", content_type="text/plain")

    async def _render_bandwidth_exceeded(request: web.Request) -> web.Response:
        try:
            info = _bot_info(bot)
            return aiohttp_jinja2.render_template(
                "bandwidth_exceeded.html",
                request,
                {
                    "bot_name":       info["bot_name"],
                    "bot_username":   info["bot_username"],
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

    app = web.Application(middlewares=[security_headers_middleware, not_found_middleware])
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))

    # -----------------------------------------------------------------------
    # Public routes
    # -----------------------------------------------------------------------

    @aiohttp_jinja2.template("home.html")
    async def home(request: web.Request):
        info = _bot_info(bot)
        return {
            "bot_name":       info["bot_name"],
            "bot_username":   info["bot_username"],
            "owner_username": "FLiX_LY",
        }

    async def _tracked_stream(request: web.Request, file_hash: str, is_download: bool):
        client_ip   = _get_client_ip(request)
        session_key = f"{file_hash}:{client_ip}"
        await _register_session(session_key)
        try:
            return await streaming_service.stream_file(request, file_hash, is_download=is_download)
        except web.HTTPNotFound:
            raise
        finally:
            await _unregister_session(session_key)

    async def stream_page(request: web.Request):
        file_hash = request.match_info["file_hash"]
        accept    = request.headers.get("Accept", "")
        range_h   = request.headers.get("Range", "")

        if range_h or "text/html" not in accept:
            try:
                return await _tracked_stream(request, file_hash, is_download=False)
            except web.HTTPNotFound:
                return web.HTTPFound("/not_found.html")

        file_data = await database.get_file_by_hash(file_hash)
        if not file_data:
            return web.HTTPFound("/not_found.html")

        allowed, _ = await check_bandwidth_limit(database)
        if not allowed:
            raise web.HTTPServiceUnavailable(reason="bandwidth limit exceeded")

        base      = str(request.url.origin())
        file_type = (
            "video"   if file_data["file_type"] == Config.FILE_TYPE_VIDEO
            else "audio" if file_data["file_type"] == Config.FILE_TYPE_AUDIO
            else "document"
        )

        mime = (
            file_data.get("mime_type")
            or _mime_for_filename(
                file_data["file_name"],
                MIME_TYPE_MAP.get(file_data.get("file_type"), "application/octet-stream"),
            )
            or "application/octet-stream"
        )
        playable = is_browser_playable(mime)

        # Pre-warm the file-ID and metadata caches while the HTML page is
        # being assembled so the first byte-range request from the player
        # can start streaming immediately without a cold-cache Telegram RPC.
        import asyncio as _asyncio
        _asyncio.ensure_future(
            streaming_service.streamer.get_file_properties(str(file_data["message_id"]))
        )

        info = _bot_info(bot)
        context = {
            "bot_name":         info["bot_name"],
            "bot_username":     info["bot_username"],
            "owner_username":   "FLiX_LY",
            "file_name":        file_data["file_name"],
            "file_size":        format_size(file_data["file_size"]),
            "file_type":        file_type,
            "mime_type":        mime,
            "browser_playable": playable,
            "stream_url":       f"{base}/stream/{file_hash}",
            "download_url":     f"{base}/dl/{file_hash}",
            "telegram_url":     f"https://t.me/{info['bot_username']}?start={file_hash}",
        }
        return aiohttp_jinja2.render_template("stream.html", request, context)

    async def download_file(request: web.Request):
        file_hash = request.match_info["file_hash"]
        try:
            return await _tracked_stream(request, file_hash, is_download=True)
        except web.HTTPNotFound:
            return web.HTTPFound("/not_found.html")

    async def not_found_page(request: web.Request):
        return await _render_not_found(request)

    # -----------------------------------------------------------------------
    # Authentication routes
    # -----------------------------------------------------------------------

    async def login_page(request: web.Request):
        if _is_authenticated(request):
            return web.HTTPFound("/bot_settings")

        expired    = _session_expired(request)
        logged_out = request.rel_url.query.get("message") == "logged_out"
        csrf       = _new_csrf_token()

        context = {
            "csrf_token": csrf,
            "error":      request.rel_url.query.get("error", ""),
            "message":    "Your session expired due to inactivity. Please log in again." if expired else "",
            "logged_out": logged_out,
        }
        return aiohttp_jinja2.render_template("login.html", request, context)

    async def login_post(request: web.Request):
        client_ip = _get_client_ip(request)

        if not _check_rate_limit(client_ip):
            return web.Response(
                status=429,
                text="Too many login attempts. Please wait a minute and try again.",
                content_type="text/plain",
            )

        try:
            data = await request.post()
        except Exception:
            return web.HTTPFound("/login?error=invalid_request")

        csrf_token = data.get("csrf_token", "")
        if not _validate_csrf(csrf_token):
            return web.HTTPFound("/login?error=invalid_csrf")

        username = data.get("username", "").strip()
        password = data.get("password", "")

        admin_user = os.environ.get("ADMIN_USERNAME", "admin")
        admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")

        if not admin_hash:
            # First-time setup fallback: plaintext from ADMIN_PASSWORD env var
            admin_plain = os.environ.get("ADMIN_PASSWORD", "admin")
            valid = (username == admin_user and password == admin_plain)
        else:
            valid = (username == admin_user and _verify_password(password, admin_hash))

        if not valid:
            logger.warning("Failed login attempt from IP %s", client_ip)
            return web.HTTPFound("/login?error=invalid_credentials")

        token    = _create_session()
        response = web.HTTPFound("/bot_settings")
        response.set_cookie(
            "session_token",
            token,
            httponly=True,
            secure=False,   # Set True in production with HTTPS
            samesite="Strict",
            max_age=int(_SESSION_LIFETIME.total_seconds()),
        )
        return response

    async def logout(request: web.Request):
        _destroy_session(request)
        response = web.HTTPFound("/login?message=logged_out")
        response.del_cookie("session_token", path="/")
        return response

    # -----------------------------------------------------------------------
    # Protected: Bot Settings panel
    # -----------------------------------------------------------------------

    async def bot_settings_page(request: web.Request):
        if not _is_authenticated(request):
            return web.HTTPFound("/login")
        try:
            ctx = await _collect_panel_data()
            return aiohttp_jinja2.render_template("bot_settings.html", request, ctx)
        except Exception as exc:
            logger.error("bot_settings page error: %s", exc)
            return web.Response(status=500, text="Internal server error")

    # -----------------------------------------------------------------------
    # Protected: Admin APIs
    # -----------------------------------------------------------------------

    def _require_auth(handler):
        async def wrapper(request: web.Request):
            if not _is_authenticated(request):
                return web.json_response({"error": "Unauthorized"}, status=401)
            return await handler(request)
        return wrapper

    @_require_auth
    async def api_stats(request: web.Request):
        try:
            stats    = await database.get_stats()
            bw_stats = await database.get_bandwidth_stats()
            max_bw   = Config.get("max_bandwidth", 107374182400)
            bw_used  = bw_stats["total_bandwidth"]
            bw_today = bw_stats["today_bandwidth"]
            bw_pct   = round((bw_used / max_bw * 100) if max_bw else 0, 1)

            try:
                ram          = psutil.virtual_memory()
                cpu_pct      = psutil.cpu_percent(interval=None)
                ram_used_fmt = format_size(ram.used)
            except Exception:
                cpu_pct      = 0
                ram_used_fmt = "N/A"

            uptime_str = _format_uptime(time.time() - Config.UPTIME if Config.UPTIME else 0)

            payload = {
                "total_users": stats.get("total_users", 0),
                "total_chats": stats.get("total_users", 0),
                "total_files": stats.get("total_files", 0),
                "ram_used":    ram_used_fmt,
                "cpu_pct":     cpu_pct,
                "uptime":      uptime_str,
                "bw_pct":      bw_pct,
                "bw_used":     format_size(bw_used),
                "bw_today":    format_size(bw_today),
                "bw_limit":    format_size(max_bw),
            }
            return web.Response(text=json.dumps(payload), content_type="application/json")
        except Exception as exc:
            logger.error("api_stats error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    @_require_auth
    async def api_bandwidth(request: web.Request):
        try:
            stats     = await database.get_bandwidth_stats()
            max_bw    = Config.get("max_bandwidth", 107374182400)
            bw_mode   = Config.get("bandwidth_mode", True)
            used      = stats["total_bandwidth"]
            today     = stats["today_bandwidth"]
            remaining = max(0, max_bw - used)
            pct       = round((used / max_bw * 100) if max_bw else 0, 1)
            payload = {
                **stats,
                "limit":          max_bw,
                "remaining":      remaining,
                "percentage":     pct,
                "bandwidth_mode": bw_mode,
                "formatted": {
                    "total_bandwidth": format_size(used),
                    "today_bandwidth": format_size(today),
                    "limit":           format_size(max_bw),
                    "remaining":       format_size(remaining),
                },
            }
            return web.Response(text=json.dumps(payload), content_type="application/json")
        except Exception as exc:
            logger.error("api_bandwidth error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    @_require_auth
    async def api_health(request: web.Request):
        try:
            info = _bot_info(bot)
            payload = {
                "status":       "ok",
                "bot_status":   "running" if getattr(bot, "me", None) else "initializing",
                "bot_name":     info["bot_name"],
                "bot_username": info["bot_username"],
                "bot_id":       info["bot_id"],
                "bot_dc":       info["bot_dc"],
                "active_conns": get_active_session_count(),
            }
            return web.Response(text=json.dumps(payload), content_type="application/json")
        except Exception as exc:
            logger.error("api_health error: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    async def stats_endpoint(request: web.Request):
        if "application/json" in request.headers.get("Accept", ""):
            return await api_stats(request)
        raise web.HTTPFound("/bot_settings")

    async def bandwidth_endpoint(request: web.Request):
        if "application/json" in request.headers.get("Accept", ""):
            return await api_bandwidth(request)
        raise web.HTTPFound("/bot_settings")

    async def health_endpoint(request: web.Request):
        if "application/json" in request.headers.get("Accept", ""):
            return await api_health(request)
        raise web.HTTPFound("/bot_settings")

    # -----------------------------------------------------------------------
    # Panel data helpers
    # -----------------------------------------------------------------------

    async def _collect_panel_data():
        try:
            stats    = await database.get_stats()
            bw_stats = await database.get_bandwidth_stats()
        except Exception:
            stats    = {"total_users": 0, "total_files": 0}
            bw_stats = {"total_bandwidth": 0, "today_bandwidth": 0}

        max_bw    = Config.get("max_bandwidth", 107374182400)
        bw_mode   = Config.get("bandwidth_mode", True)
        bw_used   = bw_stats["total_bandwidth"]
        bw_today  = bw_stats["today_bandwidth"]
        remaining = max(0, max_bw - bw_used)
        bw_pct    = round((bw_used / max_bw * 100) if max_bw else 0, 1)

        try:
            ram          = psutil.virtual_memory()
            ram_pct      = ram.percent
            ram_used_fmt = format_size(ram.used)
            cpu_pct      = psutil.cpu_percent(interval=None)
        except Exception:
            ram_pct      = 0
            ram_used_fmt = "N/A"
            cpu_pct      = 0

        uptime_seconds = time.time() - Config.UPTIME if Config.UPTIME else 0
        uptime_str     = _format_uptime(uptime_seconds)

        info = _bot_info(bot)

        return {
            **info,
            "total_users":  stats.get("total_users",  0),
            "total_chats":  stats.get("total_users",  0),
            "total_files":  stats.get("total_files",  0),
            "ram_used":     ram_used_fmt,
            "ram_pct":      ram_pct,
            "cpu_pct":      cpu_pct,
            "uptime":       uptime_str,
            "bw_mode":      bw_mode,
            "bw_limit":     format_size(max_bw),
            "bw_used":      format_size(bw_used),
            "bw_today":     format_size(bw_today),
            "bw_remaining": format_size(remaining),
            "bw_pct":       bw_pct,
            "bot_status":   "running" if getattr(bot, "me", None) else "initializing",
            "active_conns": get_active_session_count(),
        }

    def _format_uptime(seconds: float) -> str:
        seconds = int(seconds)
        d, seconds = divmod(seconds, 86400)
        h, seconds = divmod(seconds, 3600)
        m, s       = divmod(seconds, 60)
        parts = []
        if d: parts.append(f"{d}d")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    async def not_found_page(request: web.Request):
        return await _render_not_found(request)

    app.router.add_get("/",                   home)
    app.router.add_get("/stream/{file_hash}", stream_page)
    app.router.add_get("/dl/{file_hash}",     download_file)
    app.router.add_get("/not_found",          not_found_page)
    app.router.add_get("/not_found.html",     not_found_page)

    app.router.add_get("/login",              login_page)
    app.router.add_post("/login",             login_post)
    app.router.add_get("/logout",             logout)

    app.router.add_get("/bot_settings",       bot_settings_page)

    app.router.add_get("/api/stats",          api_stats)
    app.router.add_get("/api/bandwidth",      api_bandwidth)
    app.router.add_get("/api/health",         api_health)
    app.router.add_get("/api/bot_settings",   api_stats)
    app.router.add_get("/api/update_settings", api_stats)
    app.router.add_get("/api/bot_config",     api_health)

    app.router.add_get("/stats",              stats_endpoint)
    app.router.add_get("/bandwidth",          bandwidth_endpoint)
    app.router.add_get("/health",             health_endpoint)

    return app
