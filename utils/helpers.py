import secrets
import string
from config import Config
import logging

logger = logging.getLogger(__name__)


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size"""
    if bytes_size == 0:
        return '0 B'
    
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    k = 1024
    i = 0
    size = bytes_size
    
    while size >= k and i < len(sizes) - 1:
        size /= k
        i += 1
    
    return f"{size:.2f} {sizes[i]}"


def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    if not text:
        return 'Unknown File'
    
    # Replace backticks with single quotes to avoid markdown issues
    return text.replace('`', "'")


def generate_secret_token(length: int = 16) -> str:
    """Generate a random secret token"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def small_caps(text: str) -> str:
    """Convert text to small caps (Unicode small capitals)"""
    normal = "abcdefghijklmnopqrstuvwxyz"
    small_caps_chars = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ"
    
    result = []
    for char in text.lower():
        if char in normal:
            idx = normal.index(char)
            result.append(small_caps_chars[idx])
        else:
            result.append(char)
    
    return ''.join(result)


async def check_fsub(client, user_id: int) -> bool:
    """Check if user has joined the force subscription channel"""
    from pyrogram.errors import UserNotParticipant
    
    # If force sub is disabled, return True
    if not Config.get("fsub_mode", False):
        return True
    
    fsub_chat_id = Config.get("fsub_chat_id", 0)
    if not fsub_chat_id:
        return True
    
    try:
        member = await client.get_chat_member(fsub_chat_id, user_id)
        # Check if user is member, admin, or creator
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.error(f"Force sub check error: {e}")
        return True  # On error, allow access
