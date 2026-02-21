import logging
from config import Config

logger = logging.getLogger(__name__)


def format_size(bytes_size: int) -> str:
    if not bytes_size:
        return "0 B"
    sizes = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_size)
    i = 0
    while size >= 1024 and i < len(sizes) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {sizes[i]}"


def escape_markdown(text: str) -> str:
    if not text:
        return "Unknown File"
    return text.replace("`", "'")


def small_caps(text: str) -> str:
    normal = "abcdefghijklmnopqrstuvwxyz"
    small  = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ"
    result = []
    for char in text.lower():
        idx = normal.find(char)
        result.append(small[idx] if idx != -1 else char)
    return "".join(result)


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
        logger.error("Force-sub check error: %s", e)
        return True
