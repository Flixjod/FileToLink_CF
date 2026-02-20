import logging

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import Config
from helper import small_caps, check_fsub

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private, group=1)
async def start_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/start | user=%s args=%s", user_id, message.command)

    await db.register_user({
        "user_id":    str(user_id),
        "username":   message.from_user.username   or "",
        "first_name": message.from_user.first_name or "",
        "last_name":  message.from_user.last_name  or "",
    })

    if len(message.command) > 1:
        file_hash = message.command[1]
        logger.info("deep-link | user=%s hash=%s", user_id, file_hash)

        if Config.get("fsub_mode", False):
            is_member = await check_fsub(client, user_id)
            if not is_member:
                fsub_link = Config.get("fsub_inv_link", "")
                logger.warning("fsub failed on deep-link | user=%s", user_id)
                await message.reply_text(
                    f"⚠️ *{small_caps('access denied')}*\n\n"
                    f"ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.\n\n"
                    f"📢 ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ:",
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
                logger.warning("deep-link file not found | user=%s hash=%s", user_id, file_hash)
                await message.reply_text(
                    f"❌ {small_caps('error')}: ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ",
                    reply_to_message_id=message.id,
                )
                return

            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.DUMP_CHAT_ID,
                message_id=int(file_data["message_id"]),
            )
            logger.info("file delivered via deep-link | user=%s hash=%s", user_id, file_hash)

            import asyncio
            asyncio.create_task(db.increment_downloads(file_data["message_id"], 0))
        except Exception as exc:
            logger.error("deep-link error | user=%s hash=%s err=%s", user_id, file_hash, exc)
            await message.reply_text(
                f"❌ {small_caps('error')}: ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ",
                reply_to_message_id=message.id,
            )
        return

    start_text = (
        f"👋 *{small_caps('hello')} {message.from_user.first_name}*,\n\n"
        f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
        f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜ.\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ғᴀsᴛ ᴄʜᴜɴᴋ-ʙᴀsᴇᴅ sᴛʀᴇᴀᴍɪɴɢ\n"
        f"🎬 ᴠɪᴅᴇᴏ sᴇᴇᴋɪɴɢ ᴄᴀᴘᴀʙɪʟɪᴛʏ\n"
        f"📥 ʀᴇsᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅs\n"
        f"🔐 sᴇᴄᴜʀᴇ ғɪʟᴇ ʟɪɴᴋs\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/help  — ɢᴇᴛ ʜᴇʟᴘ\n"
        f"/about — ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ\n"
        f"/files — ᴠɪᴇᴡ ʏᴏᴜʀ ғɪʟᴇs\n"
        f"/stats — ᴠɪᴇᴡ sᴛᴀᴛɪsᴛɪᴄs"
    )

    if user_id in Config.OWNER_ID:
        start_text += (
            f"\n\n*{small_caps('owner commands')}:*\n"
            f"/setpublic    — ᴛᴏɢɢʟᴇ ᴘᴜʙʟɪᴄ/ᴘʀɪᴠᴀᴛᴇ\n"
            f"/addsudo      — ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ\n"
            f"/setbandwidth — sᴇᴛ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ\n"
            f"/broadcast    — ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ"
        )

    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]]

    if Config.Start_IMG:
        try:
            await message.reply_photo(
                photo=Config.Start_IMG,
                caption=start_text,
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return
        except Exception as exc:
            logger.warning("failed to send start photo | user=%s err=%s", user_id, exc)

    await message.reply_text(
        start_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("help") & filters.private, group=1)
async def help_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info("/help | user=%s", user_id)

    help_text = (
        f"📚 *{small_caps('help & guide')}*\n\n"
        f"*{small_caps('how to use')}:*\n"
        f"1️⃣ sᴇɴᴅ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        f"2️⃣ ɢᴇᴛ ɪɴsᴛᴀɴᴛ sᴛʀᴇᴀᴍ ʟɪɴᴋs\n"
        f"3️⃣ sʜᴀʀᴇ ʟɪɴᴋs ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"*{small_caps('supported files')}:*\n"
        f"🎬 ᴠɪᴅᴇᴏs (ᴍᴘ4, ᴍᴋᴠ, ᴀᴠɪ, …)\n"
        f"🎵 ᴀᴜᴅɪᴏ (ᴍᴘ3, ᴍ4ᴀ, ғʟᴀᴄ, …)\n"
        f"📄 ᴅᴏᴄᴜᴍᴇɴᴛs (ᴘᴅғ, ᴢɪᴘ, …)\n"
        f"🖼️ ɪᴍᴀɢᴇs (ᴊᴘɢ, ᴘɴɢ, …)\n\n"
        f"*{small_caps('commands')}:*\n"
        f"/start  — sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        f"/files  — ᴠɪᴇᴡ ʏᴏᴜʀ ғɪʟᴇs\n"
        f"/stats  — ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs\n"
        f"/about  — ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ\n\n"
        f"💡 *{small_caps('tip')}:* ᴜsᴇ /revoke <token> ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ғɪʟᴇs"
    )

    await message.reply_text(
        help_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )


@Client.on_message(filters.command("about") & filters.private, group=1)
async def about_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/about | user=%s", user_id)

    try:
        stats = await db.get_stats()
    except Exception as exc:
        logger.error("failed to fetch stats for /about | err=%s", exc)
        stats = {"total_files": 0, "total_users": 0, "total_downloads": 0}

    about_text = (
        f"ℹ️ *{small_caps('about filestream bot')}*\n\n"
        f"🤖 *{small_caps('bot name')}:* FileStream Bot\n"
        f"👤 *{small_caps('username')}:* @{Config.BOT_USERNAME}\n"
        f"📊 *{small_caps('total files')}:* {stats['total_files']}\n"
        f"👥 *{small_caps('total users')}:* {stats['total_users']}\n"
        f"📥 *{small_caps('downloads')}:* {stats['total_downloads']}\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ʜɪɢʜ-ᴘᴇʀғᴏʀᴍᴀɴᴄᴇ ᴄʜᴜɴᴋ sᴛʀᴇᴀᴍɪɴɢ\n"
        f"🎯 ʀᴀɴɢᴇ ʀᴇQᴜᴇsᴛ sᴜᴘᴘᴏʀᴛ\n"
        f"🔐 sᴇᴄᴜʀᴇ ғɪʟᴇ ʟɪɴᴋs\n"
        f"💾 ᴍᴏɴɢᴏᴅʙ sᴛᴏʀᴀɢᴇ\n"
        f"📊 ʙᴀɴᴅᴡɪᴅᴛʜ ᴄᴏɴᴛʀᴏʟ\n\n"
        f"💻 *{small_caps('developer')}:* @FLiX_LY\n"
        f"🐍 *{small_caps('framework')}:* Pyrogram + aiohttp\n"
        f"⚡ *{small_caps('version')}:* 2.0"
    )

    await message.reply_text(
        about_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
