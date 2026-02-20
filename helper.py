import secrets
import string
import logging
from config import Config

logger = logging.getLogger(__name__)


# ── Size formatting ────────────────────────────────────────────────────────

def format_size(bytes_size: int) -> str:
    if not bytes_size:
        return "0 B"
    sizes = ["B", "KB", "MB", "GB", "TB"]
    size  = float(bytes_size)
    i     = 0
    while size >= 1024 and i < len(sizes) - 1:
        size /= 1024
        i    += 1
    return f"{size:.2f} {sizes[i]}"


def escape_markdown(text: str) -> str:
    if not text:
        return "Unknown File"
    return text.replace("`", "'")


def generate_secret_token(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def small_caps(text: str) -> str:
    normal = "abcdefghijklmnopqrstuvwxyz"
    small  = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ"
    result = []
    for char in text.lower():
        idx = normal.find(char)
        result.append(small[idx] if idx != -1 else char)
    return "".join(result)


# ── Force-subscription check ───────────────────────────────────────────────

async def check_fsub(client, user_id: int) -> bool:
    from pyrogram.errors import UserNotParticipant
    from pyrogram.enums import ChatMemberStatus

    if not Config.get("fsub_mode", False):
        return True
    fsub_chat_id = Config.get("fsub_chat_id", 0)
    if not fsub_chat_id:
        return True
    try:
        member = await client.get_chat_member(fsub_chat_id, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.error("fsub check error: %s", e)
        return True


# ── Bandwidth / access checks ──────────────────────────────────────────────

async def check_bandwidth_limit(db):
    try:
        stats  = await db.get_bandwidth_stats()
        max_bw = Config.get("max_bandwidth", 107374182400)
        if stats["total_bandwidth"] >= max_bw:
            return False, stats
        return True, stats
    except Exception as e:
        logger.error("bandwidth check error: %s", e)
        return True, {}


async def check_user_access(db, user_id: int) -> bool:
    if Config.get("public_bot", False):
        return True
    if user_id in Config.OWNER_ID:
        return True
    return await db.is_sudo_user(str(user_id))


# ── Cryptic (HMAC hash helpers) ────────────────────────────────────────────

import hmac
import hashlib


class Cryptic:

    @staticmethod
    def generate_random_token(length: int = 12) -> str:
        return secrets.token_urlsafe(length)[:length]

    @staticmethod
    def hash_file_id(message_id: str) -> str:
        payload   = f"{message_id}:{Config.SECRET_KEY}"
        signature = hmac.new(
            Config.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature[:24]

    @staticmethod
    def verify_hash(file_hash: str, message_id: str) -> bool:
        try:
            expected = Cryptic.hash_file_id(message_id)
            return hmac.compare_digest(file_hash, expected)
        except Exception:
            return False

    @staticmethod
    def dehash_file_id(hashed: str) -> str:
        if not hashed or len(hashed) != 24:
            raise ValueError("Invalid hash format – must be 24 hex characters")
        try:
            int(hashed, 16)
        except ValueError:
            raise ValueError("Invalid hash format – must be hexadecimal")
        return hashed
