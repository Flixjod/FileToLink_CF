"""
Middleware helpers for aiohttp request processing
"""
import logging
from aiohttp import web
from database import Database
from config import Config

logger = logging.getLogger(__name__)


async def check_bandwidth_limit(db: Database):
    """
    Check if the global bandwidth limit has been exceeded.
    Returns (allowed: bool, stats: dict).
    """
    try:
        stats = await db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            return False, stats
        return True, stats
    except Exception as e:
        logger.error(f"Bandwidth check error: {e}")
        return True, {}


async def check_user_access(db: Database, user_id: int) -> bool:
    """Return True if the user is allowed to upload / access bot features."""
    if Config.get("public_bot", False):
        return True
    if user_id in Config.OWNER_ID:
        return True
    return await db.is_sudo_user(str(user_id))


def bandwidth_middleware(db: Database):
    """
    aiohttp middleware factory that blocks requests when bandwidth is exhausted.
    Attach to the aiohttp Application with app.middlewares.
    """
    @web.middleware
    async def middleware(request: web.Request, handler):
        allowed, stats = await check_bandwidth_limit(db)
        if not allowed:
            return web.json_response(
                {
                    "error": "Bandwidth limit exceeded",
                    "used":  stats.get("total_bandwidth", 0),
                    "limit": Config.get("max_bandwidth", 0),
                },
                status=503,
            )
        return await handler(request)
    return middleware
