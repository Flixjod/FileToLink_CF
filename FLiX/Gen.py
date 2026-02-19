"""
File Generation and Management Commands
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from utils import Cryptic, format_size, escape_markdown, generate_secret_token, small_caps, check_fsub
from config import Config
# File-type constants now live in Config
FILE_TYPE_VIDEO    = Config.FILE_TYPE_VIDEO
FILE_TYPE_AUDIO    = Config.FILE_TYPE_AUDIO
FILE_TYPE_IMAGE    = Config.FILE_TYPE_IMAGE
FILE_TYPE_DOCUMENT = Config.FILE_TYPE_DOCUMENT
STREAMABLE_TYPES   = Config.STREAMABLE_TYPES
import logging

logger = logging.getLogger(__name__)


async def check_access(user_id: int) -> bool:
    """Check if user has access to bot features"""
    from database import db
    
    # Public bot - everyone has access (if not force sub)
    if Config.get("public_bot", False):
        return True
    
    # Owner always has access
    if user_id in Config.OWNER_ID:
        return True
    
    # Check sudo users
    return await db.is_sudo_user(str(user_id))


@Client.on_message((filters.document | filters.video | filters.audio | filters.photo) & filters.private)
async def file_handler(client: Client, message: Message):
    """Handle file uploads"""
    from database import db
    
    # Check force subscription first
    if Config.get("fsub_mode", False):
        is_member = await check_fsub(client, message.from_user.id)
        if not is_member:
            fsub_link = Config.get("fsub_inv_link", "")
            await message.reply_text(
                f"⚠️ *{small_caps('access denied')}*\n\n"
                f"ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=fsub_link)
                ]])
            )
            return
    
    # Check access
    if not await check_access(message.from_user.id):
        await message.reply_text(
            f"❌ *{small_caps('access forbidden')}*\n\n"
            f"📡 ᴛʜɪs ɪs ᴀ ᴘʀɪᴠᴀᴛᴇ ʙᴏᴛ."
        )
        return
    
    # Check bandwidth limit
    stats = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    if stats["total_bandwidth"] >= max_bandwidth:
        await message.reply_text(
            f"❌ *{small_caps('bandwidth limit reached')}!*\n\n"
            f"ᴛʜᴇ ʙᴏᴛ ʜᴀs ʀᴇᴀᴄʜᴇᴅ ɪᴛs ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ.\n"
            f"ᴘʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ."
        )
        return
    
    # Extract file info
    if message.document:
        file = message.document
        file_name = file.file_name or "Document"
        file_size = file.file_size
        file_type = file.mime_type.split("/")[0] if file.mime_type else "document"
        telegram_file_id = file.file_id
    elif message.video:
        file = message.video
        file_name = file.file_name or "Video File"
        file_size = file.file_size
        file_type = FILE_TYPE_VIDEO
        telegram_file_id = file.file_id
    elif message.audio:
        file = message.audio
        file_name = file.file_name or "Audio File"
        file_size = file.file_size
        file_type = FILE_TYPE_AUDIO
        telegram_file_id = file.file_id
    elif message.photo:
        file = message.photo
        file_name = f"{file.file_unique_id}.jpg"
        file_size = file.file_size
        file_type = FILE_TYPE_IMAGE
        telegram_file_id = file.file_id
    else:
        await message.reply_text(f"❌ ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ғɪʟᴇ ᴛʏᴘᴇ")
        return
    
    # Check file size
    max_file_size = Config.get("max_telegram_size", 4294967296)
    if file_size > max_file_size:
        await message.reply_text(
            f"❌ *{small_caps('file too large')}*\n\n"
            f"📊 *{small_caps('file size')}:* `{format_size(file_size)}`\n"
            f"⚠️ *{small_caps('max allowed')}:* `{format_size(max_file_size)}`\n\n"
            f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ sᴍᴀʟʟᴇʀ ғɪʟᴇ."
        )
        return
    
    # Send processing message
    processing_msg = await message.reply_text("⏳ ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...")
    
    # Forward to dump channel
    try:
        forwarded = await message.copy(Config.DUMP_CHAT_ID)
        
        # Log to logs channel if configured
        if Config.LOGS_CHAT_ID:
            try:
                user_mention = message.from_user.mention
                log_text = (
                    f"#NewFile\n\n"
                    f"👤 User: {user_mention}\n"
                    f"🆔 ID: `{message.from_user.id}`\n"
                    f"📁 File: `{file_name}`\n"
                    f"💾 Size: `{format_size(file_size)}`\n"
                    f"📊 Type: `{file_type}`"
                )
                await client.send_message(Config.LOGS_CHAT_ID, log_text)
            except Exception as e:
                logger.error(f"Failed to send log: {e}")
        
    except Exception as e:
        logger.error(f"Error forwarding to channel: {e}")
        await processing_msg.edit_text(f"❌ ᴇʀʀᴏʀ ғᴏʀᴡᴀʀᴅɪɴɢ ᴛᴏ ᴄʜᴀɴɴᴇʟ: {str(e)}")
        return
    
    # Generate hash and links
    file_hash = Cryptic.hash_file_id(str(forwarded.id))
    secret_token = generate_secret_token()
    
    # Get base URL
    base_url = Config.URL
    if not base_url:
        base_url = f"http://localhost:{Config.PORT}"
    
    stream_page = f"{base_url}/streampage?file={file_hash}"
    stream_link = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"
    
    # Register user
    await db.register_user({
        "user_id": str(message.from_user.id),
        "username": message.from_user.username or "",
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or ""
    })
    
    # Save to database
    await db.add_file({
        "file_id": file_hash,
        "message_id": str(forwarded.id),
        "telegram_file_id": telegram_file_id,
        "user_id": str(message.from_user.id),
        "username": message.from_user.username or "",
        "file_name": file_name,
        "file_size": file_size,
        "file_type": file_type,
        "mime_type": file.mime_type if hasattr(file, 'mime_type') else "",
        "secret_token": secret_token
    })
    
    # Create buttons
    is_streamable = file_type in STREAMABLE_TYPES
    
    buttons = []
    if is_streamable:
        buttons.append([
            InlineKeyboardButton(f"🌐 {small_caps('stream page')}", url=stream_page),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)
        ])
    else:
        buttons.append([
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash)
        ],
        [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}", callback_data=f"revoke_{secret_token}")]
    ])
    
    # Create message
    safe_name = escape_markdown(file_name)
    formatted_size = format_size(file_size)
    
    text = (
        f"✅ *{small_caps('file successfully processed')}!*\n\n"
        f"📂 *{small_caps('file name')}:* `{safe_name}`\n"
        f"💾 *{small_caps('file size')}:* `{formatted_size}`\n"
        f"📊 *{small_caps('file type')}:* `{file_type}`\n"
        f"🔐 *{small_caps('secret token')}:* `{secret_token}`\n"
    )
    
    if is_streamable:
        text += f"🎬 *{small_caps('streaming')}:* `Available`\n\n"
        text += f"🔗 *{small_caps('stream link')}:*\n`{stream_link}`"
        
        max_stream_size = Config.get("max_stream_size", 2147483648)
        if file_size > max_stream_size:
            text += f"\n\n⚠️ *{small_caps('note')}:* sᴛʀᴇᴀᴍɪɴɢ ᴡᴏʀᴋs ʙᴇsᴛ ғᴏʀ ғɪʟᴇs ᴜɴᴅᴇʀ {format_size(max_stream_size)}."
    else:
        text += f"\n🔗 *{small_caps('download link')}:*\n`{download_link}`"
    
    text += f"\n\n💡 *{small_caps('tip')}:* ᴜsᴇ /revoke {secret_token} ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜɪs ғɪʟᴇ ᴀɴʏᴛɪᴍᴇ."
    
    await processing_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_message(filters.command("files") & filters.private)
async def files_command(client: Client, message: Message):
    """Handle /files command"""
    from database import db
    
    user_id = str(message.from_user.id)
    
    # Check access
    if not await check_access(message.from_user.id):
        await message.reply_text(f"❌ {small_caps('access forbidden')}")
        return
    
    files = await db.get_user_files(user_id, limit=50)
    
    if not files:
        await message.reply_text(
            f"📂 *{small_caps('your files')}*\n\n"
            f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғɪʟᴇs ʏᴇᴛ. sᴇɴᴅ ᴍᴇ ᴀ ғɪʟᴇ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ!"
        )
        return
    
    buttons = []
    for file in files[:10]:
        file_name = file["file_name"]
        if len(file_name) > 30:
            file_name = file_name[:27] + '...'
        buttons.append([InlineKeyboardButton(f"📄 {file_name}", callback_data=f"view_{file['message_id']}")])
    
    text = f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs:"
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_message(filters.command("revoke") & filters.private)
async def revoke_command(client: Client, message: Message):
    """Handle /revoke command"""
    from database import db
    
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ *{small_caps('invalid command')}*\n\n"
            f"ᴜsᴀɢᴇ: `/revoke <secret_token>`"
        )
        return
    
    token = message.command[1]
    file_data = await db.get_file_by_token(token)
    
    if not file_data:
        await message.reply_text(
            f"❌ *{small_caps('file not found')}*\n\n"
            f"ᴛʜᴇ ғɪʟᴇ ᴡɪᴛʜ ᴛʜɪs ᴛᴏᴋᴇɴ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ ᴏʀ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
        )
        return
    
    # Check permission
    if file_data["user_id"] != str(message.from_user.id) and message.from_user.id not in Config.OWNER_ID:
        await message.reply_text(
            f"❌ *{small_caps('permission denied')}*\n\n"
            f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʀᴇᴠᴏᴋᴇ ᴛʜɪs ғɪʟᴇ."
        )
        return
    
    # Delete from dump channel
    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
    
    # Delete from database
    await db.delete_file(file_data["message_id"])
    
    await message.reply_text(
        f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
        f"📂 *{small_caps('file')}:* `{escape_markdown(file_data['file_name'])}`\n\n"
        f"ᴀʟʟ ʟɪɴᴋs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ ᴀɴᴅ ᴛʜᴇ ғɪʟᴇ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀᴄᴄᴇssɪʙʟᴇ."
    )


@Client.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message):
    """Handle /stats command"""
    from database import db
    
    # Check access
    if not await check_access(message.from_user.id):
        await message.reply_text(f"❌ {small_caps('access forbidden')}")
        return
    
    stats = await db.get_stats()
    
    text = (
        f"📊 *{small_caps('bot statistics')}*\n\n"
        f"📂 *{small_caps('total files')}:* `{stats['total_files']}`\n"
        f"👥 *{small_caps('total users')}:* `{stats['total_users']}`\n"
        f"📥 *{small_caps('total downloads')}:* `{stats['total_downloads']}`\n"
        f"📊 *{small_caps('total bandwidth')}:* `{format_size(stats['total_bandwidth'])}`\n"
        f"📊 *{small_caps('today bandwidth')}:* `{format_size(stats['today_bandwidth'])}`"
    )
    
    await message.reply_text(text)


@Client.on_message(filters.command("bandwidth") & filters.private)
async def bandwidth_command(client: Client, message: Message):
    """Handle /bandwidth command"""
    from database import db
    
    # Only owner and sudo users can check bandwidth
    if message.from_user.id not in Config.OWNER_ID and not await db.is_sudo_user(str(message.from_user.id)):
        await message.reply_text(f"❌ {small_caps('permission denied')}")
        return
    
    stats = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    total_bandwidth = stats["total_bandwidth"]
    remaining = max_bandwidth - total_bandwidth
    percentage = (total_bandwidth / max_bandwidth) * 100 if max_bandwidth > 0 else 0
    
    # Progress bar
    bar_length = 20
    filled = int(bar_length * percentage / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    text = (
        f"📊 *{small_caps('bandwidth usage')}*\n\n"
        f"📈 *{small_caps('total used')}:* `{format_size(total_bandwidth)}`\n"
        f"📉 *{small_caps('remaining')}:* `{format_size(remaining)}`\n"
        f"📊 *{small_caps('limit')}:* `{format_size(max_bandwidth)}`\n"
        f"📊 *{small_caps('percentage')}:* `{percentage:.2f}%`\n\n"
        f"`{bar}` {percentage:.1f}%\n\n"
        f"📥 *{small_caps('today bandwidth')}:* `{format_size(stats['today_bandwidth'])}`\n"
        f"📥 *{small_caps('today downloads')}:* `{stats['today_downloads']}`"
    )
    
    if remaining < (max_bandwidth * 0.1):
        text += f"\n\n⚠️ *{small_caps('warning')}:* ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ɴᴇᴀʀɪɴɢ!"
    
    await message.reply_text(text)
