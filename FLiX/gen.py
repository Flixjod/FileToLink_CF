import logging

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from helper import Cryptic, format_size, escape_markdown, small_caps, check_fsub

logger = logging.getLogger(__name__)

FILE_TYPE_VIDEO    = "video"
FILE_TYPE_AUDIO    = "audio"
FILE_TYPE_IMAGE    = "image"
FILE_TYPE_DOCUMENT = "document"

STREAMABLE_TYPES = [FILE_TYPE_VIDEO, FILE_TYPE_AUDIO]

MIME_TYPE_MAP = {
    FILE_TYPE_VIDEO:    "video/mp4",
    FILE_TYPE_AUDIO:    "audio/mpeg",
    FILE_TYPE_IMAGE:    "image/jpeg",
    FILE_TYPE_DOCUMENT: "application/octet-stream",
}


async def check_access(user_id: int) -> bool:
    from database import db
    if Config.get("public_bot", False):
        return True
    if user_id in Config.OWNER_ID:
        return True
    return await db.is_sudo_user(str(user_id))


@Client.on_message(
    (filters.document | filters.video | filters.audio | filters.photo) & filters.private,
    group=0,
)
async def file_handler(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    if Config.get("fsub_mode", False):
        is_member = await check_fsub(client, user_id)
        if not is_member:
            fsub_link = Config.get("fsub_inv_link", "")
            await client.send_message(
                chat_id=message.chat.id,
                text=(
                    f"⚠️ *{small_caps('access denied')}*\n\n"
                    f"ʏᴏᴜ ᴍᴜꜱᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜꜱᴇ ᴛʜɪꜱ ʙᴏᴛ."
                ),
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=fsub_link)
                ]]),
            )
            return

    if not await check_access(user_id):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ *{small_caps('access forbidden')}*\n\n📡 ᴛʜɪꜱ ɪꜱ ᴀ ᴘʀɪᴠᴀᴛᴇ ʙᴏᴛ.",
            reply_to_message_id=message.id,
        )
        return

    stats = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    if stats["total_bandwidth"] >= max_bandwidth:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('bandwidth limit reached')}!*\n\n"
                f"ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀ."
            ),
            reply_to_message_id=message.id,
        )
        return

    if message.document:
        file      = message.document
        file_name = file.file_name or "Document"
        file_size = file.file_size
        file_type = file.mime_type.split("/")[0] if file.mime_type else FILE_TYPE_DOCUMENT
        telegram_file_id = file.file_id
    elif message.video:
        file      = message.video
        file_name = file.file_name or "Video File"
        file_size = file.file_size
        file_type = FILE_TYPE_VIDEO
        telegram_file_id = file.file_id
    elif message.audio:
        file      = message.audio
        file_name = file.file_name or "Audio File"
        file_size = file.file_size
        file_type = FILE_TYPE_AUDIO
        telegram_file_id = file.file_id
    elif message.photo:
        file      = message.photo
        file_name = f"{file.file_unique_id}.jpg"
        file_size = file.file_size
        file_type = FILE_TYPE_IMAGE
        telegram_file_id = file.file_id
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ᴜɴꜱᴜᴘᴘᴏʀᴛᴇᴅ ꜰɪʟᴇ ᴛʏᴘᴇ",
            reply_to_message_id=message.id,
        )
        return

    max_file_size = Config.get("max_telegram_size", 4294967296)
    if file_size > max_file_size:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('file too large')}*\n\n"
                f"📊 *{small_caps('file size')}:* `{format_size(file_size)}`\n"
                f"⚠️ *{small_caps('max allowed')}:* `{format_size(max_file_size)}`"
            ),
            reply_to_message_id=message.id,
        )
        return

    processing_msg = await client.send_message(
        chat_id=message.chat.id,
        text="⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʏᴏᴜʀ ꜰɪʟᴇ...",
        reply_to_message_id=message.id,
    )

    try:
        file_info = await message.copy(Config.DUMP_CHAT_ID)
    except Exception as exc:
        logger.error("failed to copy to dump channel: user=%s err=%s", user_id, exc)
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ ᴇʀʀᴏʀ ꜰᴏʀᴡᴀʀᴅɪɴɢ ᴛᴏ ᴄʜᴀɴɴᴇʟ: {exc}",
            reply_to_message_id=message.id,
        )
        await processing_msg.delete()
        return

    file_hash = Cryptic.hash_file_id(str(file_info.id))

    await client.send_message(
        chat_id=Config.DUMP_CHAT_ID,
        text=f'''
RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ : {message.from_user.first_name}
Uꜱᴇʀ ɪᴅ : {message.from_user.id}
Fɪʟᴇ ɪᴅ : {file_hash}
''',
        reply_to_message_id=file_info.id,
        disable_web_page_preview=True,
    )

    if Config.LOGS_CHAT_ID:
        try:
            await client.send_message(
                chat_id=Config.LOGS_CHAT_ID,
                text=(
                    f"#NewFile\n\n"
                    f"👤 User: {message.from_user.mention}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"📁 File: `{file_name}`\n"
                    f"💾 Size: `{format_size(file_size)}`\n"
                    f"📊 Type: `{file_type}`"
                ),
            )
        except Exception as exc:
            logger.error("failed to send log message: %s", exc)

    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"

    await db.register_user({
        "user_id":    str(user_id),
        "username":   message.from_user.username   or "",
        "first_name": message.from_user.first_name or "",
        "last_name":  message.from_user.last_name  or "",
    })
    await db.add_file({
        "file_id":          file_hash,
        "message_id":       str(file_info.id),
        "telegram_file_id": telegram_file_id,
        "user_id":          str(user_id),
        "username":         message.from_user.username or "",
        "file_name":        file_name,
        "file_size":        file_size,
        "file_type":        file_type,
        "mime_type":        getattr(file, "mime_type", ""),
    })

    is_streamable = file_type in STREAMABLE_TYPES
    buttons = []

    if is_streamable:
        buttons.append([
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])

    buttons.extend([
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
        [InlineKeyboardButton(
            f"🗑️ {small_caps('revoke')}",
            callback_data=f"revoke_{file_hash}",
        )],
    ])

    safe_name      = escape_markdown(file_name)
    formatted_size = format_size(file_size)

    text = (
        f"✅ *{small_caps('file successfully processed')}!*\n\n"
        f"📂 *{small_caps('file name')}:* `{safe_name}`\n"
        f"💾 *{small_caps('file size')}:* `{formatted_size}`\n"
        f"📊 *{small_caps('file type')}:* `{file_type}`\n"
    )
    if is_streamable:
        text += f"🎬 *{small_caps('streaming')}:* `Available`\n\n"
        text += f"🔗 *{small_caps('stream link')}:*\n`{stream_link}`"
    else:
        text += f"\n🔗 *{small_caps('download link')}:*\n`{download_link}`"

    text += f"\n\n💡 *{small_caps('tip')}:* ᴜꜱᴇ /revoke {file_hash} ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜɪꜱ ꜰɪʟᴇ ᴀɴʏᴛɪᴍᴇ."

    await processing_msg.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("files") & filters.private, group=0)
async def files_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    if not await check_access(user_id):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ {small_caps('access forbidden')}",
            reply_to_message_id=message.id,
        )
        return

    files = await db.get_user_files(str(user_id), limit=50)

    if not files:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"📂 *{small_caps('your files')}*\n\n"
                f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ. "
                f"ꜱᴇɴᴅ ᴍᴇ ᴀ ꜰɪʟᴇ ᴛᴏ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ!"
            ),
            reply_to_message_id=message.id,
        )
        return

    buttons = []
    for f in files[:10]:
        name = f["file_name"]
        if len(name) > 30:
            name = name[:27] + "..."
        buttons.append([
            InlineKeyboardButton(f"📄 {name}", callback_data=f"view_{f['message_id']}")
        ])

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\n"
            f"ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ:"
        ),
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("revoke") & filters.private, group=0)
async def revoke_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    if len(message.command) < 2:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('invalid command')}*\n\n"
                f"ᴜꜱᴀɢᴇ: `/revoke <file_hash>`"
            ),
            reply_to_message_id=message.id,
        )
        return

    file_hash = message.command[1]
    file_data = await db.get_file_by_hash(file_hash)

    if not file_data:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('file not found')}*\n\n"
                f"ᴛʜᴇ ꜰɪʟᴇ ᴅᴏᴇꜱɴ'ᴛ ᴇxɪꜱᴛ ᴏʀ ʜᴀꜱ ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
            ),
            reply_to_message_id=message.id,
        )
        return

    if file_data["user_id"] != str(user_id) and user_id not in Config.OWNER_ID:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('permission denied')}*\n\n"
                f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴛᴏ ʀᴇᴠᴏᴋᴇ ᴛʜɪꜱ ꜰɪʟᴇ."
            ),
            reply_to_message_id=message.id,
        )
        return

    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as exc:
        logger.error("error deleting dump message: msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
            f"📂 *{small_caps('file')}:* `{escape_markdown(file_data['file_name'])}`\n\n"
            f"ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
        ),
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("stats") & filters.private, group=0)
async def stats_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    if not await check_access(user_id):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ {small_caps('access forbidden')}",
            reply_to_message_id=message.id,
        )
        return

    stats = await db.get_stats()
    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"📊 *{small_caps('bot statistics')}*\n\n"
            f"📂 *{small_caps('total files')}:* `{stats['total_files']}`\n"
            f"👥 *{small_caps('total users')}:* `{stats['total_users']}`\n"
            f"📥 *{small_caps('total downloads')}:* `{stats['total_downloads']}`\n"
            f"📊 *{small_caps('total bandwidth')}:* `{format_size(stats['total_bandwidth'])}`\n"
            f"📊 *{small_caps('today bandwidth')}:* `{format_size(stats['today_bandwidth'])}`"
        ),
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("bandwidth") & filters.private, group=0)
async def bandwidth_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    if user_id not in Config.OWNER_ID and not await db.is_sudo_user(str(user_id)):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ {small_caps('permission denied')}",
            reply_to_message_id=message.id,
        )
        return

    stats         = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    total         = stats["total_bandwidth"]
    remaining     = max_bandwidth - total
    percentage    = (total / max_bandwidth * 100) if max_bandwidth else 0

    bar_length = 20
    filled     = int(bar_length * percentage / 100)
    bar        = "█" * filled + "░" * (bar_length - filled)

    text = (
        f"📊 *{small_caps('bandwidth usage')}*\n\n"
        f"📈 *{small_caps('total used')}:* `{format_size(total)}`\n"
        f"📉 *{small_caps('remaining')}:* `{format_size(remaining)}`\n"
        f"📊 *{small_caps('limit')}:* `{format_size(max_bandwidth)}`\n"
        f"📊 *{small_caps('percentage')}:* `{percentage:.2f}%`\n\n"
        f"`{bar}` {percentage:.1f}%\n\n"
        f"📥 *{small_caps('today bandwidth')}:* `{format_size(stats['today_bandwidth'])}`\n"
        f"📥 *{small_caps('today downloads')}:* `{stats['today_downloads']}`"
    )

    if remaining < (max_bandwidth * 0.1):
        text += f"\n\n⚠️ *{small_caps('warning')}:* ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ɴᴇᴀʀɪɴɢ!"

    await client.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_to_message_id=message.id,
    )
