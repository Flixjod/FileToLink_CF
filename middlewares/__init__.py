"""
Middleware functions for Flask request processing
"""
from functools import wraps
from flask import request, jsonify
from database import Database
from config import Config
import logging

logger = logging.getLogger(__name__)


async def check_bandwidth_limit(db: Database):
    """Check if bandwidth limit has been exceeded"""
    try:
        stats = await db.get_bandwidth_stats()
        if stats["total_bandwidth"] >= Config.MAX_BANDWIDTH:
            return False, stats
        return True, stats
    except Exception as e:
        logger.error(f"Bandwidth check error: {e}")
        return True, None


async def check_user_access(db: Database, user_id: int) -> bool:
    """Check if user has access to bot features"""
    # Public bot - everyone has access
    if Config.PUBLIC_BOT:
        return True
    
    # Owner always has access
    if user_id == Config.BOT_OWNER:
        return True
    
    # Check sudo users
    return await db.is_sudo_user(str(user_id))


def require_bandwidth(db: Database):
    """Decorator to check bandwidth before processing request"""
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            allowed, stats = await check_bandwidth_limit(db)
            if not allowed:
                return jsonify({
                    "error": "Bandwidth limit exceeded",
                    "used": stats.get("total_bandwidth", 0),
                    "limit": Config.MAX_BANDWIDTH
                }), 503
            return await f(*args, **kwargs)
        return wrapper
    return decorator
