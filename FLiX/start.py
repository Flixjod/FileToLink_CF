import logging

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database import db
from helper import small_caps, format_size, escape_markdown, check_fsub

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private, group=1)
async def start_command(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    is_new = await db.register_user_on_start({
        "user_id":    str(user_id),
        "username":   user.username   or "",
        "first_name": user.first_name or "",
        "last_name":  user.last_name  or "",
    })

    # ── Log new user to log channel ──────────────────────────────────────
    if is_new and Config.LOGS_CHAT_ID:
        try:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            await client.send_message(
                chat_id=Config.LOGS_CHAT_ID,
                text=(
                    "#NewUser\n\n"
                    f"👤 **User:** {user.mention}\n"
                    f"🆔 **ID:** `{user_id}`\n"
                    f"👤 **Username:** @{user.username or 'N/A'}\n"
                    f"📛 **Name:** `{full_name}`"
                ),
            )
        except Exception as exc:
            logger.error("failed to log new user: %s", exc)

    # ── Deep-link (file hash in /start arg) ─────────────────────────────
    if len(message.command) > 1:
        file_hash = message.command[1]

        if Config.get("fsub_mode", False):
            if not await check_fsub(client, message):
                return

        try:
            file_data = await db.get_file_by_hash(file_hash)
            if not file_data:
                await client.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"❌ **{small_caps('file not found')}**\n\n"
                        "ᴛʜᴇ ꜰɪʟᴇ ʟɪɴᴋ ɪꜱ ɪɴᴠᴀʟɪᴅ ᴏʀ ʜᴀꜱ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
                    ),
                    reply_to_message_id=message.id,
                )
                return

            base_url      = Config.URL or f"http://localhost:{Config.PORT}"
            stream_link   = f"{base_url}/stream/{file_hash}"
            download_link = f"{base_url}/dl/{file_hash}"

            file_type     = file_data.get("file_type", "document")
            is_streamable = file_type in ("video", "audio")
            safe_name     = escape_markdown(file_data["file_name"])
            fmt_size      = format_size(file_data["file_size"])

            text = (
                f"✅ **{small_caps('file found')}!**\n\n"
                f"📂 **{small_caps('name')}:** `{safe_name}`\n"
                f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
                f"📊 **{small_caps('type')}:** `{file_type}`\n\n"
            )

            btn_rows = []
            if is_streamable:
                text += f"🎬 **{small_caps('stream link')}:**\n`{stream_link}`"
                btn_rows.append([
                    InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
                    InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
                ])
            else:
                text += f"🔗 **{small_caps('download link')}:**\n`{download_link}`"
                btn_rows.append([
                    InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
                ])

            await client.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup(btn_rows),
            )

        except Exception as exc:
            logger.error("deep-link error: user=%s hash=%s err=%s", user_id, file_hash, exc)
            await client.send_message(
                chat_id=message.chat.id,
                text=f"❌ `{small_caps('error')}`: ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ",
                reply_to_message_id=message.id,
            )
        return

    # ── Welcome message ──────────────────────────────────────────────────
    start_text = (
        f"👋 **Hello {message.from_user.first_name}**,\n\n"
        f"ɪ ᴀᴍ ᴀ **{small_caps('premium file stream bot')}**.\n\n"
        f"📂 **{small_caps('send me any file')}** (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        "ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ꜱᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ꜰᴏʀ ʏᴏᴜ."
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
        f"📚 **{small_caps('help & guide')}**\n\n"
        f"**{small_caps('how to use')}:**\n"
        "1️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        "2️⃣ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ꜱᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ\n"
        "3️⃣ ꜱʜᴀʀᴇ ʟɪɴᴋꜱ ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"**{small_caps('supported files')}:**\n"
        "🎬 ᴠɪᴅᴇᴏꜱ\n🎵 ᴀᴜᴅɪᴏ\n📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ\n🖼️ ɪᴍᴀɢᴇꜱ"
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
    about_text = (
        f"ℹ️ **{small_caps('about filestream bot')}**\n\n"
        f"🤖 **{small_caps('bot')}:** @{Config.BOT_USERNAME}\n\n"
        f"💻 **{small_caps('developer')}:** @FLiX_LY\n"
        f"⚡ **{small_caps('version')}:** 2.1"
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=about_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )


@Client.on_callback_query(filters.regex(r"^start$"), group=2)
async def cb_start(client: Client, callback: CallbackQuery):
    text = (
        f"👋 **Hello {callback.from_user.first_name}**,\n\n"
        f"ɪ ᴀᴍ ᴀ **{small_caps('premium file stream bot')}**.\n\n"
        f"📂 **{small_caps('send me any file')}** (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        "ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ꜱᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ꜰᴏʀ ʏᴏᴜ."
    )
    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^help$"), group=1)
async def cb_help(client: Client, callback: CallbackQuery):
    text = (
        f"📚 **{small_caps('help & guide')}**\n\n"
        f"**{small_caps('how to use')}:**\n"
        "1️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        "2️⃣ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ꜱᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ\n"
        "3️⃣ ꜱʜᴀʀᴇ ʟɪɴᴋꜱ ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"**{small_caps('supported files')}:**\n"
        "🎬 ᴠɪᴅᴇᴏꜱ\n🎵 ᴀᴜᴅɪᴏ\n📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ\n🖼️ ɪᴍᴀɢᴇꜱ"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^about$"), group=1)
async def cb_about(client: Client, callback: CallbackQuery):
    text = (
        f"ℹ️ **{small_caps('about filestream bot')}**\n\n"
        f"🤖 **{small_caps('bot')}:** @{Config.BOT_USERNAME}\n\n"
        f"💻 **{small_caps('developer')}:** @FLiX_LY\n"
        f"⚡ **{small_caps('version')}:** 2.1"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
    await callback.answer()
