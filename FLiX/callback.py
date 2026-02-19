"""
Callback Query Handlers
"""
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from utils import escape_markdown, format_size, small_caps
import logging

logger = logging.getLogger(__name__)


@Client.on_callback_query()
async def callback_handler(client: Client, callback: CallbackQuery):
    """Handle all callback queries"""
    from database import db
    
    data = callback.data
    user_id = str(callback.from_user.id)
    
    # Start callback
    if data == "start":
        start_text = (
            f"👋 *{small_caps('hello')} {callback.from_user.first_name}*,\n\n"
            f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
            f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
            f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜ.\n\n"
            f"*{small_caps('features')}:*\n"
            f"⚡ ғᴀsᴛ sᴛʀᴇᴀᴍɪɴɢ\n"
            f"🎬 ᴠɪᴅᴇᴏ sᴇᴇᴋɪɴɢ\n"
            f"📥 ʀᴇsᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅs\n"
            f"🔐 sᴇᴄᴜʀᴇ ʟɪɴᴋs"
        )
        
        buttons = [[
            InlineKeyboardButton(f"📚 {small_caps('help')}", callback_data="help"),
            InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about")
        ]]
        
        await callback.message.edit_text(start_text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback.answer()
    
    # Help callback
    elif data == "help":
        help_text = (
            f"📚 *{small_caps('help & guide')}*\n\n"
            f"*{small_caps('how to use')}:*\n"
            f"1️⃣ sᴇɴᴅ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
            f"2️⃣ ɢᴇᴛ ɪɴsᴛᴀɴᴛ sᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋs\n"
            f"3️⃣ sʜᴀʀᴇ ʟɪɴᴋs ᴀɴʏᴡʜᴇʀᴇ!\n\n"
            f"*{small_caps('supported files')}:*\n"
            f"🎬 ᴠɪᴅᴇᴏs\n"
            f"🎵 ᴀᴜᴅɪᴏ\n"
            f"📄 ᴅᴏᴄᴜᴍᴇɴᴛs\n"
            f"🖼️ ɪᴍᴀɢᴇs"
        )
        
        buttons = [[InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start")]]
        
        await callback.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback.answer()
    
    # About callback
    elif data == "about":
        stats = await db.get_stats()
        
        about_text = (
            f"ℹ️ *{small_caps('about filestream bot')}*\n\n"
            f"🤖 *{small_caps('bot')}:* @{Config.BOT_USERNAME}\n"
            f"📊 *{small_caps('files')}:* {stats['total_files']}\n"
            f"👥 *{small_caps('users')}:* {stats['total_users']}\n"
            f"📥 *{small_caps('downloads')}:* {stats['total_downloads']}\n\n"
            f"💻 *{small_caps('developer')}:* @FLiX_LY\n"
            f"⚡ *{small_caps('version')}:* 2.0"
        )
        
        buttons = [[InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start")]]
        
        await callback.message.edit_text(about_text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback.answer()
    
    # Revoke file callback
    elif data.startswith("revoke_"):
        token = data.replace("revoke_", "")
        file_data = await db.get_file_by_token(token)
        
        if not file_data:
            await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
            return
        
        # Check permission
        if file_data["user_id"] != user_id and callback.from_user.id not in Config.OWNER_ID:
            await callback.answer("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ", show_alert=True)
            return
        
        # Delete from dump channel
        try:
            await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
        
        # Delete from database
        await db.delete_file(file_data["message_id"])
        
        # Edit message
        await callback.message.edit_text(
            f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
            f"ᴀʟʟ ʟɪɴᴋs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
        )
        await callback.answer("✅ ғɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)
    
    # View file details callback
    elif data.startswith("view_"):
        message_id = data.replace("view_", "")
        file_data = await db.get_file(message_id)
        
        if not file_data:
            await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ", show_alert=True)
            return
        
        # Generate links
        file_hash = file_data["file_id"]
        base_url = Config.URL or f"http://localhost:{Config.PORT}"
        
        stream_page = f"{base_url}/streampage?file={file_hash}"
        stream_link = f"{base_url}/stream/{file_hash}"
        download_link = f"{base_url}/dl/{file_hash}"
        telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"
        
        safe_name = escape_markdown(file_data["file_name"])
        formatted_size = format_size(file_data["file_size"])
        
        buttons = [
            [
                InlineKeyboardButton(f"🌐 {small_caps('stream')}", url=stream_page),
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link)
            ],
            [
                InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
                InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash)
            ],
            [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}", callback_data=f"revoke_{file_data['secret_token']}")],
            [InlineKeyboardButton(f"⬅️ {small_caps('back')}", callback_data="back_to_files")]
        ]
        
        text = (
            f"✅ *{small_caps('file details')}*\n\n"
            f"📂 *{small_caps('name')}:* `{safe_name}`\n"
            f"💾 *{small_caps('size')}:* `{formatted_size}`\n"
            f"📊 *{small_caps('type')}:* `{file_data['file_type']}`\n"
            f"📥 *{small_caps('downloads')}:* `{file_data.get('downloads', 0)}`\n"
            f"📅 *{small_caps('uploaded')}:* `{file_data['created_at'].strftime('%Y-%m-%d')}`"
        )
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback.answer()
    
    # Back to files list callback
    elif data == "back_to_files":
        files = await db.get_user_files(user_id, limit=50)
        
        if not files:
            await callback.message.edit_text(
                f"📂 *{small_caps('your files')}*\n\n"
                f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғɪʟᴇs ʏᴇᴛ."
            )
            await callback.answer()
            return
        
        buttons = []
        for file in files[:10]:
            file_name = file["file_name"]
            if len(file_name) > 30:
                file_name = file_name[:27] + '...'
            buttons.append([InlineKeyboardButton(f"📄 {file_name}", callback_data=f"view_{file['message_id']}")])
        
        text = f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ғɪʟᴇ:"
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        await callback.answer()
    
    else:
        await callback.answer("❌ ɪɴᴠᴀʟɪᴅ ᴄᴀʟʟʙᴀᴄᴋ", show_alert=True)
