import logging

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import Config
from helper import small_caps, check_fsub

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private, group=1)
async def start_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id

    await db.register_user({
        "user_id":    str(user_id),
        "username":   message.from_user.username   or "",
        "first_name": message.from_user.first_name or "",
        "last_name":  message.from_user.last_name  or "",
    })

    if len(message.command) > 1:
        file_hash = message.command[1]

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
                        InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=fsub_link),
                    ], [
                        InlineKeyboardButton(
                            "🔄 ᴛʀʏ ᴀɢᴀɪɴ",
                            url=f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}",
                        ),
                    ]]),
                )
                return

        try:
            file_data = await db.get_file_by_hash(file_hash)
            if not file_data:
                await client.send_message(
                    chat_id=message.chat.id,
                    text=f"❌ {small_caps('error')}: ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ",
                    reply_to_message_id=message.id,
                )
                return

            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.DUMP_CHAT_ID,
                message_id=int(file_data["message_id"]),
            )

            import asyncio
            asyncio.create_task(db.increment_downloads(file_data["message_id"], 0))

        except Exception as exc:
            logger.error("deep-link error: user=%s hash=%s err=%s", user_id, file_hash, exc)
            await client.send_message(
                chat_id=message.chat.id,
                text=f"❌ {small_caps('error')}: ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ",
                reply_to_message_id=message.id,
            )
        return

    start_text = (
        f"👋 *{small_caps('hello')} {message.from_user.first_name}*,\n\n"
        f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
        f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ꜱᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ꜰᴏʀ ʏᴏᴜ.\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ꜰᴀꜱᴛ ꜱᴛʀᴇᴀᴍɪɴɢ ᴡɪᴛʜ ʀᴀɴɢᴇ ꜱᴜᴘᴘᴏʀᴛ\n"
        f"🎬 ᴠɪᴅᴇᴏ ꜱᴇᴇᴋɪɴɢ ᴄᴀᴘᴀʙɪʟɪᴛʏ\n"
        f"📥 ʀᴇꜱᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅꜱ\n"
        f"🔐 ꜱᴇᴄᴜʀᴇ ꜰɪʟᴇ ʟɪɴᴋꜱ\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/help  — ɢᴇᴛ ʜᴇʟᴘ\n"
        f"/about — ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ\n"
        f"/files — ᴠɪᴇᴡ ʏᴏᴜʀ ꜰɪʟᴇꜱ\n"
        f"/stats — ᴠɪᴇᴡ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ"
    )

    if user_id in Config.OWNER_ID:
        start_text += (
            f"\n\n*{small_caps('owner commands')}:*\n"
            f"/setpublic    — ᴛᴏɢɢʟᴇ ᴘᴜʙʟɪᴄ/ᴘʀɪᴠᴀᴛᴇ\n"
            f"/addsudo      — ᴀᴅᴅ ꜱᴜᴅᴏ ᴜꜱᴇʀ\n"
            f"/setbandwidth — ꜱᴇᴛ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ\n"
            f"/broadcast    — ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ"
        )

    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]]

    if Config.Start_IMG:
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=Config.Start_IMG,
                caption=start_text,
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return
        except Exception as exc:
            logger.warning("failed to send start photo: user=%s err=%s", user_id, exc)

    await client.send_message(
        chat_id=message.chat.id,
        text=start_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("help") & filters.private, group=1)
async def help_command(client: Client, message: Message):
    help_text = (
        f"📚 *{small_caps('help & guide')}*\n\n"
        f"*{small_caps('how to use')}:*\n"
        f"1️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        f"2️⃣ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ꜱᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ\n"
        f"3️⃣ ꜱʜᴀʀᴇ ʟɪɴᴋꜱ ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"*{small_caps('supported files')}:*\n"
        f"🎬 ᴠɪᴅᴇᴏꜱ (ᴍᴘ4, ᴍᴋᴠ, ᴀᴠɪ, …)\n"
        f"🎵 ᴀᴜᴅɪᴏ (ᴍᴘ3, ᴍ4ᴀ, ꜰʟᴀᴄ, …)\n"
        f"📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ (ᴘᴅꜰ, ᴢɪᴘ, …)\n"
        f"🖼️ ɪᴍᴀɢᴇꜱ (ᴊᴘɢ, ᴘɴɢ, …)\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/start  — ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        f"/files  — ᴠɪᴇᴡ ʏᴏᴜʀ ꜰɪʟᴇꜱ\n"
        f"/stats  — ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
        f"/about  — ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ\n\n"
        f"💡 *{small_caps('tip')}:* ᴜꜱᴇ /revoke <file_hash> ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ꜰɪʟᴇꜱ"
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=help_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )


@Client.on_message(filters.command("about") & filters.private, group=1)
async def about_command(client: Client, message: Message):
    from database import db

    try:
        stats = await db.get_stats()
    except Exception as exc:
        logger.error("failed to fetch stats for /about: %s", exc)
        stats = {"total_files": 0, "total_users": 0, "total_downloads": 0}

    about_text = (
        f"ℹ️ *{small_caps('about filestream bot')}*\n\n"
        f"🤖 *{small_caps('bot name')}:* FileStream Bot\n"
        f"👤 *{small_caps('username')}:* @{Config.BOT_USERNAME}\n"
        f"📊 *{small_caps('total files')}:* {stats['total_files']}\n"
        f"👥 *{small_caps('total users')}:* {stats['total_users']}\n"
        f"📥 *{small_caps('downloads')}:* {stats['total_downloads']}\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ʜɪɢʜ-ᴘᴇʀꜰᴏʀᴍᴀɴᴄᴇ ꜱᴛʀᴇᴀᴍɪɴɢ\n"
        f"🎯 ʀᴀɴɢᴇ ʀᴇQᴜᴇꜱᴛ ꜱᴜᴘᴘᴏʀᴛ\n"
        f"🔐 ꜱᴇᴄᴜʀᴇ ꜰɪʟᴇ ʟɪɴᴋꜱ\n"
        f"💾 ᴍᴏɴɢᴏᴅʙ ꜱᴛᴏʀᴀɢᴇ\n"
        f"📊 ʙᴀɴᴅᴡɪᴅᴛʜ ᴄᴏɴᴛʀᴏʟ\n\n"
        f"💻 *{small_caps('developer')}:* @FLiX_LY\n"
        f"🐍 *{small_caps('framework')}:* Pyrogram + aiohttp\n"
        f"⚡ *{small_caps('version')}:* 2.0"
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=about_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
