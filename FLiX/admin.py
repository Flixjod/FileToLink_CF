"""
Admin Commands (Owner only)
"""
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from utils import small_caps, format_size
import logging

logger = logging.getLogger(__name__)


# Owner filter
def owner_filter(_, __, message: Message):
    return message.from_user.id in Config.OWNER_ID

owner = filters.create(owner_filter)


@Client.on_message(filters.command("setpublic") & filters.private & owner)
async def setpublic_command(client: Client, message: Message):
    """Toggle public/private mode"""
    from database import db
    
    current = Config.get("public_bot", False)
    new_value = not current
    
    await Config.update(db.db, {"public_bot": new_value})
    
    mode = "ᴘᴜʙʟɪᴄ" if new_value else "ᴘʀɪᴠᴀᴛᴇ"
    await message.reply_text(f"✅ ʙᴏᴛ ᴍᴏᴅᴇ sᴇᴛ ᴛᴏ: *{mode}*")


@Client.on_message(filters.command("addsudo") & filters.private & owner)
async def addsudo_command(client: Client, message: Message):
    """Add sudo user"""
    from database import db
    
    if len(message.command) < 2:
        await message.reply_text(f"❌ ᴜsᴀɢᴇ: `/addsudo <user_id>`")
        return
    
    try:
        user_id = message.command[1]
        await db.add_sudo_user(user_id, str(message.from_user.id))
        await message.reply_text(f"✅ ᴜsᴇʀ `{user_id}` ᴀᴅᴅᴇᴅ ᴀs sᴜᴅᴏ ᴜsᴇʀ")
    except Exception as e:
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")


@Client.on_message(filters.command("rmsudo") & filters.private & owner)
async def rmsudo_command(client: Client, message: Message):
    """Remove sudo user"""
    from database import db
    
    if len(message.command) < 2:
        await message.reply_text(f"❌ ᴜsᴀɢᴇ: `/rmsudo <user_id>`")
        return
    
    try:
        user_id = message.command[1]
        result = await db.remove_sudo_user(user_id)
        if result:
            await message.reply_text(f"✅ ᴜsᴇʀ `{user_id}` ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ sᴜᴅᴏ ᴜsᴇʀs")
        else:
            await message.reply_text(f"❌ ᴜsᴇʀ `{user_id}` ɴᴏᴛ ғᴏᴜɴᴅ")
    except Exception as e:
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")


@Client.on_message(filters.command("sudolist") & filters.private & owner)
async def sudolist_command(client: Client, message: Message):
    """List all sudo users"""
    from database import db
    
    sudo_users = await db.get_sudo_users()
    
    if not sudo_users:
        await message.reply_text(f"📋 *{small_caps('sudo users')}*\n\nɴᴏ sᴜᴅᴏ ᴜsᴇʀs ғᴏᴜɴᴅ.")
        return
    
    text = f"📋 *{small_caps('sudo users')}* ({len(sudo_users)})\n\n"
    for user in sudo_users:
        text += f"• `{user['user_id']}`\n"
    
    await message.reply_text(text)


@Client.on_message(filters.command("setbandwidth") & filters.private & owner)
async def setbandwidth_command(client: Client, message: Message):
    """Set bandwidth limit"""
    from database import db
    
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
        await Config.update(db.db, {"max_bandwidth": new_limit})
        await message.reply_text(
            f"✅ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ sᴇᴛ ᴛᴏ: `{format_size(new_limit)}`"
        )
    except ValueError:
        await message.reply_text(f"❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ғᴏʀᴍᴀᴛ")


@Client.on_message(filters.command("setfsub") & filters.private & owner)
async def setfsub_command(client: Client, message: Message):
    """Enable/disable force subscription"""
    from database import db
    
    current = Config.get("fsub_mode", False)
    new_value = not current
    
    await Config.update(db.db, {"fsub_mode": new_value})
    
    status = "ᴇɴᴀʙʟᴇᴅ" if new_value else "ᴅɪsᴀʙʟᴇᴅ"
    await message.reply_text(f"✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ: *{status}*")


@Client.on_message(filters.command("broadcast") & filters.private & owner)
async def broadcast_command(client: Client, message: Message):
    """Broadcast message to all users"""
    from database import db
    
    if not message.reply_to_message:
        await message.reply_text(
            f"❌ *{small_caps('usage')}:*\n\n"
            f"ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ `/broadcast` ᴛᴏ sᴇɴᴅ ɪᴛ ᴛᴏ ᴀʟʟ ᴜsᴇʀs"
        )
        return
    
    # Get all users
    users = await db.users.find({}).to_list(length=None)
    
    if not users:
        await message.reply_text("❌ ɴᴏ ᴜsᴇʀs ғᴏᴜɴᴅ")
        return
    
    status_msg = await message.reply_text(f"📢 sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ {len(users)} ᴜsᴇʀs...")
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await message.reply_to_message.copy(chat_id=int(user['user_id']))
            success += 1
        except Exception as e:
            logger.error(f"Broadcast failed for user {user['user_id']}: {e}")
            failed += 1
    
    await status_msg.edit_text(
        f"✅ *{small_caps('broadcast completed')}*\n\n"
        f"📤 *{small_caps('sent')}:* {success}\n"
        f"❌ *{small_caps('failed')}:* {failed}"
    )


@Client.on_message(filters.command("revokeall") & filters.private & owner)
async def revokeall_command(client: Client, message: Message):
    """Delete all files"""
    from database import db
    
    stats = await db.get_stats()
    total_files = stats["total_files"]
    
    if total_files == 0:
        await message.reply_text(f"📂 ɴᴏ ғɪʟᴇs ᴛᴏ ᴅᴇʟᴇᴛᴇ.")
        return
    
    await message.reply_text(
        f"⚠️ *{small_caps('warning')}*\n\n"
        f"ᴛʜɪs ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ *{total_files}* ғɪʟᴇs.\n"
        f"sᴇɴᴅ `/confirmdelete` ᴛᴏ ᴄᴏɴғɪʀᴍ."
    )


@Client.on_message(filters.command("confirmdelete") & filters.private & owner)
async def confirmdelete_command(client: Client, message: Message):
    """Confirm delete all files"""
    from database import db
    
    msg = await message.reply_text(f"🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ғɪʟᴇs...")
    
    deleted_count = await db.delete_all_files()
    
    await msg.edit_text(
        f"🗑️ *{small_caps('all files deleted')}!*\n\n"
        f"ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ғɪʟᴇs."
    )


@Client.on_message(filters.command("logs") & filters.private & owner)
async def logs_command(client: Client, message: Message):
    """Get bot logs"""
    try:
        with open("bot.log", "r") as f:
            logs = f.read()[-4000:]  # Last 4000 characters
        
        await message.reply_text(f"```\n{logs}\n```")
    except FileNotFoundError:
        await message.reply_text("❌ ʟᴏɢ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ")
    except Exception as e:
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
