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


def format_uptime(seconds: float) -> str:
    """Convert seconds into a human-readable uptime string."""
    seconds = int(seconds)
    days,    seconds = divmod(seconds, 86400)
    hours,   seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def human_size(n: int) -> str:
    """Return a short human-readable file size (used for log display)."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


async def check_owner(client, event) -> bool:
    """Return True if the event sender is a bot owner; send denial otherwise."""
    from pyrogram.types import Message, CallbackQuery

    user_id = event.from_user.id
    if user_id not in Config.OWNER_ID:
        if isinstance(event, Message):
            await client.send_message(
                chat_id=event.chat.id,
                text="🚫 **Access Denied!**\n\n🔒 This command is restricted to bot owners.",
                reply_to_message_id=event.id,
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "🚫 Access Denied!\n\n🔒 This action is restricted to bot owners.",
                show_alert=True,
            )
        return False
    return True


async def check_fsub(client, message_or_user_id, target_id: int = None) -> bool:
    from pyrogram.errors import UserNotParticipant, ChatAdminRequired
    from pyrogram.enums import ChatMemberStatus
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

    check_id = target_id or Config.get("fsub_chat_id", 0)
    if check_id == 0:
        return True

    enforce_fsub = target_id is None and Config.get("fsub_mode", False)
    if target_id is None and not enforce_fsub:
        return True

    # Support both a Message object and a plain user_id int
    if isinstance(message_or_user_id, int):
        user_id = message_or_user_id
        message = None
    else:
        message = message_or_user_id
        user_id = message.from_user.id

    try:
        member = await client.get_chat_member(check_id, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )

    except UserNotParticipant:
        if target_id is None and message is not None:
            await client.send_photo(
                chat_id=message.chat.id,
                photo="https://t.me/FLiX_Logos/331",
                caption=(
                    f"ʜᴇʏ **{message.from_user.mention}**,\n\n"
                    "🧩 ᴛᴏ ᴜɴʟᴏᴄᴋ ᴍʏ ғᴜʟʟ ғᴇᴀᴛᴜʀᴇ ꜱᴇᴛ,\n"
                    "ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇꜱ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!\n\n"
                    "🚀 ᴊᴏɪɴ ɴᴏᴡ, ᴛʜᴇɴ ʜɪᴛ **/start** ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ʏᴏᴜʀ ᴍɪꜱꜱɪᴏɴ."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✨ ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ ✨", url=Config.get("fsub_inv_link"))]]
                ),
            )
        return False

    except ChatAdminRequired:
        logger.warning(f"Bot lacks permission to check membership in chat {check_id}.")
        return True

    except Exception as e:
        logger.error(f"Membership check failed for user {user_id} in chat {check_id}: {e}")
        return True
