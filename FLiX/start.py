"""
Start, Help, About commands
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from utils import small_caps
import logging

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    from database import db
    
    user_id = str(message.from_user.id)
    
    # Register user
    await db.register_user({
        "user_id": user_id,
        "username": message.from_user.username or "",
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or ""
    })
    
    # Check for deep link (file access)
    if len(message.command) > 1:
        file_hash = message.command[1]
        
        # Check force subscription
        if Config.get("fsub_mode", False):
            from utils import check_fsub
            is_member = await check_fsub(client, message.from_user.id)
            if not is_member:
                fsub_link = Config.get("fsub_inv_link", "")
                await message.reply_text(
                    f"⚠️ *{small_caps('access denied')}*\n\n"
                    f"ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.\n\n"
                    f"📢 ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=fsub_link)
                    ], [
                        InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", url=f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}")
                    ]])
                )
                return
        
        try:
            # Get file from database using hash
            file_data = await db.get_file_by_hash(file_hash)
            
            if not file_data:
                await message.reply_text(f"❌ {small_caps('error')}: ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ")
                return
            
            # Forward file from dump channel
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.DUMP_CHAT_ID,
                message_id=int(file_data['message_id'])
            )
            
            # Increment download counter
            import asyncio
            asyncio.create_task(db.increment_downloads(file_data['message_id'], 0))
            
            return
        except Exception as e:
            logger.error(f"Deep link error: {e}")
            await message.reply_text(f"❌ {small_caps('error')}: ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ")
            return
    
    # Normal start message
    start_text = (
        f"👋 *{small_caps('hello')} {message.from_user.first_name}*,\n\n"
        f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
        f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜ.\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ғᴀsᴛ sᴛʀᴇᴀᴍɪɴɢ ᴡɪᴛʜ ʀᴀɴɢᴇ sᴜᴘᴘᴏʀᴛ\n"
        f"🎬 ᴠɪᴅᴇᴏ sᴇᴇᴋɪɴɢ ᴄᴀᴘᴀʙɪʟɪᴛʏ\n"
        f"📥 ʀᴇsᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅs\n"
        f"🔐 sᴇᴄᴜʀᴇ ғɪʟᴇ ʟɪɴᴋs\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/help - ɢᴇᴛ ʜᴇʟᴘ\n"
        f"/about - ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ\n"
        f"/files - ᴠɪᴇᴡ ʏᴏᴜʀ ғɪʟᴇs\n"
        f"/stats - ᴠɪᴇᴡ sᴛᴀᴛɪsᴛɪᴄs"
    )
    
    # Add owner commands if user is owner
    if message.from_user.id in Config.OWNER_ID:
        start_text += (
            f"\n\n*{small_caps('owner commands')}:*\n"
            f"/setpublic - ᴛᴏɢɢʟᴇ ᴘᴜʙʟɪᴄ/ᴘʀɪᴠᴀᴛᴇ\n"
            f"/addsudo - ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ\n"
            f"/setbandwidth - sᴇᴛ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ\n"
            f"/broadcast - ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ"
        )
    
    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}", callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about")
    ]]
    
    # Add start image if configured
    if Config.Start_IMG:
        try:
            await message.reply_photo(
                photo=Config.Start_IMG,
                caption=start_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await message.reply_text(start_text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text(start_text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = (
        f"📚 *{small_caps('help & guide')}*\n\n"
        f"*{small_caps('how to use')}:*\n"
        f"1️⃣ sᴇɴᴅ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        f"2️⃣ ɢᴇᴛ ɪɴsᴛᴀɴᴛ sᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋs\n"
        f"3️⃣ sʜᴀʀᴇ ʟɪɴᴋs ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"*{small_caps('supported files')}:*\n"
        f"🎬 ᴠɪᴅᴇᴏs (ᴍᴘ4, ᴍᴋᴠ, ᴀᴠɪ, ᴇᴛᴄ.)\n"
        f"🎵 ᴀᴜᴅɪᴏ (ᴍᴘ3, ᴍ4ᴀ, ғʟᴀᴄ, ᴇᴛᴄ.)\n"
        f"📄 ᴅᴏᴄᴜᴍᴇɴᴛs (ᴘᴅғ, ᴢɪᴘ, ᴇᴛᴄ.)\n"
        f"🖼️ ɪᴍᴀɢᴇs (ᴊᴘɢ, ᴘɴɢ, ᴇᴛᴄ.)\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/start - sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        f"/files - ᴠɪᴇᴡ ʏᴏᴜʀ ғɪʟᴇs\n"
        f"/stats - ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs\n"
        f"/about - ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ\n\n"
        f"💡 *{small_caps('tip')}:* ᴜsᴇ /revoke <token> ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ғɪʟᴇs"
    )
    
    buttons = [[InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start")]]
    
    await message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_message(filters.command("about") & filters.private)
async def about_command(client: Client, message: Message):
    """Handle /about command"""
    from database import db
    stats = await db.get_stats()
    
    about_text = (
        f"ℹ️ *{small_caps('about filestream bot')}*\n\n"
        f"🤖 *{small_caps('bot name')}:* FileStream Bot\n"
        f"👤 *{small_caps('username')}:* @{Config.BOT_USERNAME}\n"
        f"📊 *{small_caps('total files')}:* {stats['total_files']}\n"
        f"👥 *{small_caps('total users')}:* {stats['total_users']}\n"
        f"📥 *{small_caps('downloads')}:* {stats['total_downloads']}\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ʜɪɢʜ-ᴘᴇʀғᴏʀᴍᴀɴᴄᴇ sᴛʀᴇᴀᴍɪɴɢ\n"
        f"🎯 ʀᴀɴɢᴇ ʀᴇQᴜᴇsᴛ sᴜᴘᴘᴏʀᴛ\n"
        f"🔐 sᴇᴄᴜʀᴇ ғɪʟᴇ ʟɪɴᴋs\n"
        f"💾 ᴍᴏɴɢᴏᴅʙ sᴛᴏʀᴀɢᴇ\n"
        f"📊 ʙᴀɴᴅᴡɪᴅᴛʜ ᴄᴏɴᴛʀᴏʟ\n\n"
        f"💻 *{small_caps('developer')}:* @FLiX_LY\n"
        f"🐍 *{small_caps('framework')}:* Pyrogram + aiohttp\n"
        f"⚡ *{small_caps('version')}:* 2.0"
    )
    
    buttons = [[InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start")]]
    
    await message.reply_text(about_text, reply_markup=InlineKeyboardMarkup(buttons))
