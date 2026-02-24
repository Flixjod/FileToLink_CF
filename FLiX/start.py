"""
start.py — /start, /help, /about commands + their callback counterparts.

All imports are at the top of the file (no deferred imports inside functions).
Navigation flow:
    /start  → [Help] [About]
    /help   → [Home] [About]
    /about  → [Home] [Help]
"""

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


# ─────────────────────────────────────────────────────────────────────────────
#  Text builders  (keep all UI text in one place)
# ─────────────────────────────────────────────────────────────────────────────

def _build_start_text(user) -> str:
    user_id = user.id
    text = (
        f"👋 **Hello {user.first_name}**,\n\n"
        f"ɪ ᴀᴍ ᴀ **{small_caps('premium file stream bot')}**.\n\n"
        f"📂 **{small_caps('send me any file')}** (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        "ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ꜱᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ꜰᴏʀ ʏᴏᴜ.\n\n"
        f"**{small_caps('features')}:**\n"
        "⚡ ꜰᴀꜱᴛ ꜱᴛʀᴇᴀᴍɪɴɢ ᴡɪᴛʜ ʀᴀɴɢᴇ ꜱᴜᴘᴘᴏʀᴛ\n"
        "🎬 ᴠɪᴅᴇᴏ ꜱᴇᴇᴋɪɴɢ ᴄᴀᴘᴀʙɪʟɪᴛʏ\n"
        "📥 ʀᴇꜱᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅꜱ\n"
        "🔐 ꜱᴇᴄᴜʀᴇ ꜰɪʟᴇ ʟɪɴᴋꜱ\n\n"
        f"**{small_caps('commands')}:**\n"
        "`/help`  — ɢᴇᴛ ʜᴇʟᴘ\n"
        "`/about` — ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ\n"
        "`/files` — ᴠɪᴇᴡ ʏᴏᴜʀ ꜰɪʟᴇꜱ"
    )

    if user_id in Config.OWNER_ID:
        text += (
            f"\n\n**{small_caps('owner commands')}:**\n"
            "`/adminstats`   — 📊 ᴀᴅᴍɪɴ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
            "`/bot_settings` — ⚙️ ꜰᴜʟʟ ꜱᴇᴛᴛɪɴɢꜱ ᴘᴀɴᴇʟ\n"
            "`/revokeall`    — 🗑️ ʀᴇᴠᴏᴋᴇ ᴀʟʟ ꜰɪʟᴇꜱ\n"
            "`/logs`         — 📋 ᴠɪᴇᴡ ʙᴏᴛ ʟᴏɢꜱ"
        )
    return text


def _build_help_text() -> str:
    return (
        f"📚 **{small_caps('help & guide')}**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{small_caps('how to use')}:**\n"
        "1️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        "2️⃣ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ꜱᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ\n"
        "3️⃣ ꜱʜᴀʀᴇ ʟɪɴᴋꜱ ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{small_caps('supported files')}:**\n"
        "🎬 ᴠɪᴅᴇᴏꜱ (ᴍᴘ4, ᴍᴋᴠ, ᴀᴠɪ, …)\n"
        "🎵 ᴀᴜᴅɪᴏ (ᴍᴘ3, ᴍ4ᴀ, ꜰʟᴀᴄ, …)\n"
        "📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ (ᴘᴅꜰ, ᴢɪᴘ, …)\n"
        "🖼️ ɪᴍᴀɢᴇꜱ (ᴊᴘɢ, ᴘɴɢ, …)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{small_caps('commands')}:**\n"
        "`/start`  — ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        "`/files`  — ᴠɪᴇᴡ ʏᴏᴜʀ ꜰɪʟᴇꜱ\n"
        "`/about`  — ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ\n\n"
        f"💡 **{small_caps('tip')}:** ᴜꜱᴇ `/revoke <file_hash>` ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀ ꜰɪʟᴇ"
    )


def _build_about_text() -> str:
    return (
        f"ℹ️ **{small_caps('about filestream bot')}**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 **{small_caps('bot name')}:** {Config.BOT_NAME}\n"
        f"👤 **{small_caps('username')}:** @{Config.BOT_USERNAME}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{small_caps('features')}:**\n"
        "⚡ ʜɪɢʜ-ᴘᴇʀꜰᴏʀᴍᴀɴᴄᴇ ꜱᴛʀᴇᴀᴍɪɴɢ\n"
        "🎯 ʀᴀɴɢᴇ ʀᴇQᴜᴇꜱᴛ ꜱᴜᴘᴘᴏʀᴛ\n"
        "🔐 ꜱᴇᴄᴜʀᴇ ꜰɪʟᴇ ʟɪɴᴋꜱ\n"
        "💾 ᴍᴏɴɢᴏᴅʙ ꜱᴛᴏʀᴀɢᴇ\n"
        "📊 ʙᴀɴᴅᴡɪᴅᴛʜ ᴄᴏɴᴛʀᴏʟ\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💻 **{small_caps('developer')}:** @FLiX_LY\n"
        f"🐍 **{small_caps('framework')}:** Pyrogram + aiohttp\n"
        f"⚡ **{small_caps('version')}:** 2.1"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Keyboard builders
# ─────────────────────────────────────────────────────────────────────────────

def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]])


def _help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🏠 {small_caps('home')}",  callback_data="start"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]])


def _about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🏠 {small_caps('home')}",  callback_data="start"),
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
    ]])


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────

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

    # ── Log new users to log channel ─────────────────────────────────────────
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

    # ── Deep-link (file hash in /start arg) ─────────────────────────────────
    if len(message.command) > 1:
        file_hash = message.command[1]

        if Config.get("fsub_mode", False):
            if not await check_fsub(client, message):
                return

        try:
            file_data = await db.get_file_by_hash(file_hash)
            if not file_data:
                await message.reply(
                    f"❌ **{small_caps('file not found')}**\n\n"
                    "ᴛʜᴇ ꜰɪʟᴇ ʟɪɴᴋ ɪꜱ ɪɴᴠᴀʟɪᴅ ᴏʀ ʜᴀꜱ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
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

            await message.reply(text, reply_markup=InlineKeyboardMarkup(btn_rows))

        except Exception as exc:
            logger.error("deep-link error: user=%s hash=%s err=%s", user_id, file_hash, exc)
            await message.reply(f"❌ `{small_caps('error')}`: ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ")
        return

    # ── Welcome message ──────────────────────────────────────────────────────
    text    = _build_start_text(user)
    buttons = _start_keyboard()

    if Config.Start_IMG:
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=Config.Start_IMG,
                caption=text,
                reply_to_message_id=message.id,
                reply_markup=buttons,
            )
            return
        except Exception as exc:
            logger.warning("failed to send start photo: user=%s err=%s", user_id, exc)

    await message.reply(text, reply_markup=buttons)


# ─────────────────────────────────────────────────────────────────────────────
#  /help
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("help") & filters.private, group=1)
async def help_command(client: Client, message: Message):
    await message.reply(
        _build_help_text(),
        reply_markup=_help_keyboard(),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /about
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("about") & filters.private, group=1)
async def about_command(client: Client, message: Message):
    await message.reply(
        _build_about_text(),
        reply_markup=_about_keyboard(),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Callback — Home (start)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^start$"), group=2)
async def cb_start(client: Client, callback: CallbackQuery):
    user = callback.from_user
    text = _build_start_text(user)
    try:
        await callback.message.edit_text(text, reply_markup=_start_keyboard())
    except Exception:
        await callback.message.reply(text, reply_markup=_start_keyboard())
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback — Help
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^help$"), group=1)
async def cb_help(client: Client, callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            _build_help_text(),
            reply_markup=_help_keyboard(),
        )
    except Exception:
        await callback.message.reply(
            _build_help_text(),
            reply_markup=_help_keyboard(),
        )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback — About
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^about$"), group=1)
async def cb_about(client: Client, callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            _build_about_text(),
            reply_markup=_about_keyboard(),
        )
    except Exception:
        await callback.message.reply(
            _build_about_text(),
            reply_markup=_about_keyboard(),
        )
    await callback.answer()
