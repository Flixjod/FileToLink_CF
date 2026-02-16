from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from utils import Cryptic, format_size, escape_markdown, generate_secret_token, small_caps
from config import Config
import logging

logger = logging.getLogger(__name__)

# Global database instance
db = None


def setup_handlers(client: Client, database: Database):
    """Setup all bot handlers"""
    global db
    db = database
    
    @client.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message):
        """Handle /start command"""
        user_id = str(message.from_user.id)
        
        # Register user
        await db.register_user({
            "user_id": user_id,
            "username": message.from_user.username or "",
            "first_name": message.from_user.first_name or "",
            "last_name": message.from_user.last_name or ""
        })
        
        # Check for deep link
        if len(message.command) > 1:
            file_hash = message.command[1]
            try:
                message_id = Cryptic.dehash_file_id(file_hash)
                # Forward file from channel
                await client.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=Config.BOT_CHANNEL,
                    message_id=int(message_id)
                )
                return
            except Exception as e:
                logger.error(f"Deep link error: {e}")
                await message.reply_text(f"❌ {small_caps('error')}: Invalid or expired link")
                return
        
        # Normal start message
        buttons = [[InlineKeyboardButton(f"👨‍💻 {small_caps('source code')}", url=f"https://t.me/{Config.OWNER_USERNAME}")]]
        
        start_text = (
            f"👋 *{small_caps('hello')} {message.from_user.first_name}*,\n\n"
            f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
            f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
            f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜ.\n\n"
            f"*{small_caps('commands')}:*\n"
            f"/files - ᴠɪᴇᴡ ᴀʟʟ ʏᴏᴜʀ ғɪʟᴇs\n"
            f"/revoke <token> - ʀᴇᴠᴏᴋᴇ ᴀ ғɪʟᴇ\n"
            f"/stats - ᴠɪᴇᴡ sᴛᴀᴛɪsᴛɪᴄs\n"
            f"/bandwidth - ᴄʜᴇᴄᴋ ʙᴀɴᴅᴡɪᴅᴛʜ ᴜsᴀɢᴇ"
        )
        
        # Owner commands
        if message.from_user.id == Config.BOT_OWNER:
            start_text += (
                f"\n\n*{small_caps('owner commands')}:*\n"
                f"/setpublic - ᴛᴏɢɢʟᴇ ᴘᴜʙʟɪᴄ/ᴘʀɪᴠᴀᴛᴇ ᴍᴏᴅᴇ\n"
                f"/addsudo <user_id> - ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ\n"
                f"/rmsudo <user_id> - ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ ᴜsᴇʀ\n"
                f"/sudolist - ʟɪsᴛ ᴀʟʟ sᴜᴅᴏ ᴜsᴇʀs\n"
                f"/revokeall - ᴅᴇʟᴇᴛᴇ ᴀʟʟ ғɪʟᴇs\n"
                f"/setbandwidth <bytes> - sᴇᴛ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ"
            )
        
        await message.reply_text(start_text, reply_markup=InlineKeyboardMarkup(buttons))
    
    
    @client.on_message(filters.command("files") & filters.private)
    async def files_handler(client: Client, message: Message):
        """Handle /files command"""
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
        
        text = f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs ᴀɴᴅ ɢᴇᴛ ʟɪɴᴋs:"
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    
    @client.on_message(filters.command("stats") & filters.private)
    async def stats_handler(client: Client, message: Message):
        """Handle /stats command"""
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
    
    
    @client.on_message(filters.command("bandwidth") & filters.private)
    async def bandwidth_handler(client: Client, message: Message):
        """Handle /bandwidth command"""
        # Only owner and sudo users can check bandwidth
        if message.from_user.id != Config.BOT_OWNER and not await db.is_sudo_user(str(message.from_user.id)):
            await message.reply_text(f"❌ {small_caps('permission denied')}")
            return
        
        stats = await db.get_bandwidth_stats()
        total_bandwidth = stats["total_bandwidth"]
        remaining = Config.MAX_BANDWIDTH - total_bandwidth
        percentage = (total_bandwidth / Config.MAX_BANDWIDTH) * 100 if Config.MAX_BANDWIDTH > 0 else 0
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * percentage / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        text = (
            f"📊 *{small_caps('bandwidth usage')}*\n\n"
            f"📈 *{small_caps('total used')}:* `{format_size(total_bandwidth)}`\n"
            f"📉 *{small_caps('remaining')}:* `{format_size(remaining)}`\n"
            f"📊 *{small_caps('limit')}:* `{format_size(Config.MAX_BANDWIDTH)}`\n"
            f"📊 *{small_caps('percentage')}:* `{percentage:.2f}%`\n\n"
            f"`{bar}` {percentage:.1f}%\n\n"
            f"📥 *{small_caps('today bandwidth')}:* `{format_size(stats['today_bandwidth'])}`\n"
            f"📥 *{small_caps('today downloads')}:* `{stats['today_downloads']}`"
        )
        
        if remaining < (Config.MAX_BANDWIDTH * 0.1):  # Less than 10% remaining
            text += f"\n\n⚠️ *{small_caps('warning')}:* ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ɴᴇᴀʀɪɴɢ!"
        
        await message.reply_text(text)
    
    
    @client.on_message(filters.command("revoke") & filters.private)
    async def revoke_handler(client: Client, message: Message):
        """Handle /revoke command"""
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
        if file_data["user_id"] != str(message.from_user.id) and message.from_user.id != Config.BOT_OWNER:
            await message.reply_text(
                f"❌ *{small_caps('permission denied')}*\n\n"
                f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʀᴇᴠᴏᴋᴇ ᴛʜɪs ғɪʟᴇ."
            )
            return
        
        # Delete from channel
        try:
            await client.delete_messages(Config.BOT_CHANNEL, int(file_data["message_id"]))
        except Exception as e:
            logger.error(f"Error deleting message from channel: {e}")
        
        # Delete from database
        await db.delete_file(file_data["message_id"])
        
        await message.reply_text(
            f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
            f"📂 *{small_caps('file')}:* `{escape_markdown(file_data['file_name'])}`\n\n"
            f"ᴀʟʟ ʟɪɴᴋs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ ᴀɴᴅ ᴛʜᴇ ғɪʟᴇ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀᴄᴄᴇssɪʙʟᴇ."
        )
    
    
    # Owner-only commands
    @client.on_message(filters.command("setpublic") & filters.private & filters.user(Config.BOT_OWNER))
    async def setpublic_handler(client: Client, message: Message):
        """Toggle public/private mode"""
        Config.PUBLIC_BOT = not Config.PUBLIC_BOT
        mode = "ᴘᴜʙʟɪᴄ" if Config.PUBLIC_BOT else "ᴘʀɪᴠᴀᴛᴇ"
        await message.reply_text(f"✅ ʙᴏᴛ ᴍᴏᴅᴇ sᴇᴛ ᴛᴏ: *{mode}*")
    
    
    @client.on_message(filters.command("addsudo") & filters.private & filters.user(Config.BOT_OWNER))
    async def addsudo_handler(client: Client, message: Message):
        """Add sudo user"""
        if len(message.command) < 2:
            await message.reply_text(f"❌ ᴜsᴀɢᴇ: `/addsudo <user_id>`")
            return
        
        try:
            user_id = message.command[1]
            await db.add_sudo_user(user_id, str(Config.BOT_OWNER))
            await message.reply_text(f"✅ ᴜsᴇʀ `{user_id}` ᴀᴅᴅᴇᴅ ᴀs sᴜᴅᴏ ᴜsᴇʀ")
        except Exception as e:
            await message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
    
    
    @client.on_message(filters.command("rmsudo") & filters.private & filters.user(Config.BOT_OWNER))
    async def rmsudo_handler(client: Client, message: Message):
        """Remove sudo user"""
        if len(message.command) < 2:
            await message.reply_text(f"❌ ᴜsᴀɢᴇ: `/rmsudo <user_id>`")
            return
        
        try:
            user_id = message.command[1]
            result = await db.remove_sudo_user(user_id)
            if result:
                await message.reply_text(f"✅ ᴜsᴇʀ `{user_id}` ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ sᴜᴅᴏ ᴜsᴇʀs")
            else:
                await message.reply_text(f"❌ ᴜsᴇʀ `{user_id}` ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ sᴜᴅᴏ ʟɪsᴛ")
        except Exception as e:
            await message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
    
    
    @client.on_message(filters.command("sudolist") & filters.private & filters.user(Config.BOT_OWNER))
    async def sudolist_handler(client: Client, message: Message):
        """List all sudo users"""
        sudo_users = await db.get_sudo_users()
        
        if not sudo_users:
            await message.reply_text(f"📋 *{small_caps('sudo users')}*\n\nɴᴏ sᴜᴅᴏ ᴜsᴇʀs ғᴏᴜɴᴅ.")
            return
        
        text = f"📋 *{small_caps('sudo users')}* ({len(sudo_users)})\n\n"
        for user in sudo_users:
            text += f"• `{user['user_id']}`\n"
        
        await message.reply_text(text)
    
    
    @client.on_message(filters.command("revokeall") & filters.private & filters.user(Config.BOT_OWNER))
    async def revokeall_handler(client: Client, message: Message):
        """Delete all files"""
        # Get all files
        stats = await db.get_stats()
        total_files = stats["total_files"]
        
        if total_files == 0:
            await message.reply_text(f"📂 ɴᴏ ғɪʟᴇs ᴛᴏ ᴅᴇʟᴇᴛᴇ.")
            return
        
        # Confirmation message
        await message.reply_text(f"⚠️ ᴛʜɪs ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ *{total_files}* ғɪʟᴇs. sᴇɴᴅ `/confirmdelete` ᴛᴏ ᴄᴏɴғɪʀᴍ.")
    
    
    @client.on_message(filters.command("confirmdelete") & filters.private & filters.user(Config.BOT_OWNER))
    async def confirmdelete_handler(client: Client, message: Message):
        """Confirm delete all files"""
        msg = await message.reply_text(f"🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ғɪʟᴇs...")
        
        deleted_count = await db.delete_all_files()
        
        await msg.edit_text(
            f"🗑️ *{small_caps('all files deleted')}!*\n\n"
            f"ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ғɪʟᴇs ғʀᴏᴍ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ."
        )
    
    
    @client.on_message(filters.command("setbandwidth") & filters.private & filters.user(Config.BOT_OWNER))
    async def setbandwidth_handler(client: Client, message: Message):
        """Set bandwidth limit"""
        if len(message.command) < 2:
            await message.reply_text(
                f"❌ ᴜsᴀɢᴇ: `/setbandwidth <bytes>`\n\n"
                f"ᴇxᴀᴍᴘʟᴇs:\n"
                f"`/setbandwidth 107374182400` (100GB)\n"
                f"`/setbandwidth 53687091200` (50GB)"
            )
            return
        
        try:
            new_limit = int(message.command[1])
            Config.MAX_BANDWIDTH = new_limit
            await message.reply_text(
                f"✅ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ sᴇᴛ ᴛᴏ: `{format_size(new_limit)}`"
            )
        except ValueError:
            await message.reply_text(f"❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ғᴏʀᴍᴀᴛ")
    
    
    # File handler
    @client.on_message((filters.document | filters.video | filters.audio | filters.photo) & filters.private)
    async def file_handler(client: Client, message: Message):
        """Handle file uploads"""
        # Check access
        if not await check_access(message.from_user.id):
            await message.reply_text(
                f"❌ *{small_caps('access forbidden')}*\n\n"
                f"📡 ᴅᴇᴘʟᴏʏ ʏᴏᴜʀ ᴏᴡɴ ғɪʟᴇsᴛʀᴇᴀᴍ ʙᴏᴛ."
            )
            return
        
        # Check bandwidth limit
        stats = await db.get_bandwidth_stats()
        if stats["total_bandwidth"] >= Config.MAX_BANDWIDTH:
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
        elif message.video:
            file = message.video
            file_name = file.file_name or "Video File"
            file_size = file.file_size
            file_type = "video"
        elif message.audio:
            file = message.audio
            file_name = file.file_name or "Audio File"
            file_size = file.file_size
            file_type = "audio"
        elif message.photo:
            file = message.photo
            file_name = f"{file.file_unique_id}.jpg"
            file_size = file.file_size
            file_type = "image"
        else:
            await message.reply_text(f"❌ ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ғɪʟᴇ ᴛʏᴘᴇ")
            return
        
        # Check file size
        if file_size > Config.MAX_TELEGRAM_SIZE:
            await message.reply_text(
                f"❌ *{small_caps('file too large')}*\n\n"
                f"📊 *{small_caps('file size')}:* `{format_size(file_size)}`\n"
                f"⚠️ *{small_caps('max allowed')}:* `4.00 GB`\n\n"
                f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ sᴍᴀʟʟᴇʀ ғɪʟᴇ."
            )
            return
        
        # Forward to channel WITHOUT sending extra info message
        try:
            forwarded = await message.copy(Config.BOT_CHANNEL)
            
            # Extract Telegram file_id for faster future access
            telegram_file_id = ""
            if message.document:
                telegram_file_id = message.document.file_id
            elif message.video:
                telegram_file_id = message.video.file_id
            elif message.audio:
                telegram_file_id = message.audio.file_id
            elif message.photo:
                telegram_file_id = message.photo.file_id
            
        except Exception as e:
            logger.error(f"Error forwarding to channel: {e}")
            await message.reply_text(f"❌ ᴇʀʀᴏʀ ғᴏʀᴡᴀʀᴅɪɴɢ ᴛᴏ ᴄʜᴀɴɴᴇʟ: {str(e)}")
            return
        
        # Generate hash and links
        file_hash = Cryptic.hash_file_id(str(forwarded.id))
        secret_token = generate_secret_token()
        
        # Get base URL from environment
        base_url = Config.BASE_URL
        if not base_url:
            base_url = "https://your-domain.com"  # Fallback
        
        stream_page = f"{base_url}/streampage?file={file_hash}"
        stream_link = f"{base_url}/stream/{file_hash}"
        download_link = f"{base_url}/dl/{file_hash}"
        telegram_link = f"https://t.me/{(await client.get_me()).username}?start={file_hash}"
        
        # Register user
        await db.register_user({
            "user_id": str(message.from_user.id),
            "username": message.from_user.username or "",
            "first_name": message.from_user.first_name or "",
            "last_name": message.from_user.last_name or ""
        })
        
        # Save to database with telegram_file_id
        await db.add_file({
            "file_id": file_hash,
            "message_id": str(forwarded.id),
            "telegram_file_id": telegram_file_id,  # Store for faster access
            "user_id": str(message.from_user.id),
            "username": message.from_user.username or "",
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "mime_type": file.mime_type if hasattr(file, 'mime_type') else "",
            "secret_token": secret_token
        })
        
        # Create buttons
        is_streamable = file_type in ['video', 'audio']
        
        buttons = []
        if is_streamable:
            buttons.append([
                InlineKeyboardButton(f"🌐 {small_caps('stream page')}", url=stream_page),
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)
            ])
        else:
            buttons.append([
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
                InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link)
            ])
        
        buttons.extend([
            [
                InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
                InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash)
            ] if is_streamable else [InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash)],
            [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}", callback_data=f"revoke_{secret_token}")],
            [InlineKeyboardButton(f"👑 {small_caps('owner')}", url=f"https://t.me/{Config.OWNER_USERNAME}")]
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
            
            if file_size > Config.MAX_STREAM_SIZE:
                text += f"\n\n⚠️ *{small_caps('note')}:* sᴛʀᴇᴀᴍɪɴɢ ᴡᴏʀᴋs ʙᴇsᴛ ғᴏʀ ғɪʟᴇs ᴜɴᴅᴇʀ 2GB."
        else:
            text += f"\n🔗 *{small_caps('download link')}:*\n`{download_link}`"
        
        text += f"\n\n💡 *{small_caps('tip')}:* ᴜsᴇ /revoke {secret_token} ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜɪs ғɪʟᴇ ᴀɴʏᴛɪᴍᴇ."
        
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    
    # Callback query handler
    @client.on_callback_query()
    async def callback_handler(client: Client, callback: CallbackQuery):
        """Handle callback queries"""
        data = callback.data
        user_id = str(callback.from_user.id)
        
        if data.startswith("revoke_"):
            token = data.replace("revoke_", "")
            file_data = await db.get_file_by_token(token)
            
            if not file_data:
                await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
                return
            
            # Check permission
            if file_data["user_id"] != user_id and callback.from_user.id != Config.BOT_OWNER:
                await callback.answer("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ", show_alert=True)
                return
            
            # Delete from channel
            try:
                await client.delete_messages(Config.BOT_CHANNEL, int(file_data["message_id"]))
            except Exception as e:
                logger.error(f"Error deleting message: {e}")
            
            # Delete from database
            await db.delete_file(file_data["message_id"])
            
            # Edit message
            await callback.message.edit_text(
                f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
                f"ᴀʟʟ ʟɪɴᴋs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ ᴀɴᴅ ᴛʜᴇ ғɪʟᴇ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀᴄᴄᴇssɪʙʟᴇ."
            )
            await callback.answer("✅ ғɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=False)
        
        elif data.startswith("view_"):
            message_id = data.replace("view_", "")
            file_data = await db.get_file(message_id)
            
            if not file_data:
                await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ", show_alert=True)
                return
            
            # Generate links
            file_hash = file_data["file_id"]
            base_url = Config.BASE_URL or "https://your-domain.com"
            
            stream_page = f"{base_url}/streampage?file={file_hash}"
            stream_link = f"{base_url}/stream/{file_hash}"
            download_link = f"{base_url}/dl/{file_hash}"
            telegram_link = f"https://t.me/{(await client.get_me()).username}?start={file_hash}"
            
            safe_name = escape_markdown(file_data["file_name"])
            formatted_size = format_size(file_data["file_size"])
            
            buttons = [
                [
                    InlineKeyboardButton(f"🌐 {small_caps('stream page')}", url=stream_page),
                    InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)
                ],
                [
                    InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
                    InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash)
                ],
                [InlineKeyboardButton(f"🗑️ {small_caps('revoke access')}", callback_data=f"revoke_{file_data['secret_token']}")],
                [InlineKeyboardButton(f"⬅️ {small_caps('back to list')}", callback_data="back_to_files")]
            ]
            
            text = (
                f"✅ *{small_caps('file details')}*\n\n"
                f"📂 *{small_caps('file name')}:* `{safe_name}`\n"
                f"💾 *{small_caps('file size')}:* `{formatted_size}`\n"
                f"📊 *{small_caps('file type')}:* `{file_data['file_type']}`\n"
                f"📥 *{small_caps('downloads')}:* `{file_data.get('downloads', 0)}`\n"
                f"📅 *{small_caps('uploaded')}:* `{file_data['created_at'].strftime('%Y-%m-%d')}`\n\n"
                f"🔗 *{small_caps('stream link')}:*\n`{stream_link}`"
            )
            
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await callback.answer("📂 ғɪʟᴇ ᴅᴇᴛᴀɪʟs ʟᴏᴀᴅᴇᴅ", show_alert=False)
        
        elif data == "back_to_files":
            files = await db.get_user_files(user_id, limit=50)
            
            if not files:
                await callback.message.edit_text(
                    f"📂 *{small_caps('your files')}*\n\n"
                    f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғɪʟᴇs ʏᴇᴛ."
                )
                await callback.answer("ɴᴏ ғɪʟᴇs ғᴏᴜɴᴅ", show_alert=False)
                return
            
            buttons = []
            for file in files[:10]:
                file_name = file["file_name"]
                if len(file_name) > 30:
                    file_name = file_name[:27] + '...'
                buttons.append([InlineKeyboardButton(f"📄 {file_name}", callback_data=f"view_{file['message_id']}")])
            
            text = f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs:"
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await callback.answer("📂 ғɪʟᴇs ʟɪsᴛ ʟᴏᴀᴅᴇᴅ", show_alert=False)
    
    
    # Inline query handler
    @client.on_inline_query()
    async def inline_handler(client: Client, inline_query: InlineQuery):
        """Handle inline queries"""
        if not Config.PUBLIC_BOT and inline_query.from_user.id != Config.BOT_OWNER:
            results = [
                InlineQueryResultArticle(
                    title="ᴀᴄᴄᴇss ғᴏʀʙɪᴅᴅᴇɴ",
                    description="ᴅᴇᴘʟᴏʏ ʏᴏᴜʀ ᴏᴡɴ ғɪʟᴇsᴛʀᴇᴀᴍ ʙᴏᴛ",
                    input_message_content=InputTextMessageContent(
                        f"❌ *{small_caps('access forbidden')}*\n\n"
                        f"📡 ᴅᴇᴘʟᴏʏ ʏᴏᴜʀ ᴏᴡɴ ғɪʟᴇsᴛʀᴇᴀᴍ ʙᴏᴛ."
                    )
                )
            ]
            await inline_query.answer(results, cache_time=1)
            return
        
        query = inline_query.query
        if not query:
            return
        
        try:
            message_id = Cryptic.dehash_file_id(query)
            file_data = await db.get_file(message_id)
            
            if not file_data:
                results = [
                    InlineQueryResultArticle(
                        title="ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ",
                        description="ᴛʜᴇ ғɪʟᴇ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ ᴏʀ ʜᴀs ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ",
                        input_message_content=InputTextMessageContent("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ")
                    )
                ]
                await inline_query.answer(results, cache_time=1)
                return
            
            # Forward the actual file
            results = []
            # Note: Inline mode file sharing would require additional implementation
            # For now, return a text result with link
            base_url = Config.BASE_URL or "https://your-domain.com"
            download_link = f"{base_url}/dl/{query}"
            
            results = [
                InlineQueryResultArticle(
                    title=file_data["file_name"],
                    description=f"sɪᴢᴇ: {format_size(file_data['file_size'])}",
                    input_message_content=InputTextMessageContent(
                        f"📂 **{escape_markdown(file_data['file_name'])}**\n\n"
                        f"💾 sɪᴢᴇ: `{format_size(file_data['file_size'])}`\n"
                        f"🔗 ʟɪɴᴋ: {download_link}"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)],
                        [InlineKeyboardButton(f"🔁 {small_caps('send again')}", switch_inline_query_current_chat=query)]
                    ])
                )
            ]
            
            await inline_query.answer(results, cache_time=1)
            
        except Exception as e:
            logger.error(f"Inline query error: {e}")
            results = [
                InlineQueryResultArticle(
                    title="ᴇʀʀᴏʀ",
                    description="ɪɴᴠᴀʟɪᴅ ғɪʟᴇ ʜᴀsʜ",
                    input_message_content=InputTextMessageContent("❌ ɪɴᴠᴀʟɪᴅ ғɪʟᴇ ʜᴀsʜ")
                )
            ]
            await inline_query.answer(results, cache_time=1)


async def check_access(user_id: int) -> bool:
    """Check if user has access to the bot"""
    if Config.PUBLIC_BOT:
        return True
    
    if user_id == Config.BOT_OWNER:
        return True
    
    return await db.is_sudo_user(str(user_id))
