"""
gen.py — File upload handler + /files + /stats commands.

  • File handler: processes incoming media, stores in DB, returns stream/download links.
  • /files [user_id]: shows a user's file list.
      - No argument  → show caller's own files.
      - With user_id → owner-only: show that user's files, with Files_IMG banner.
  • /stats: public bot stats (total files / bandwidth).

All imports are at the top of the file.
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
from helper import Cryptic, format_size, escape_markdown, small_caps, check_fsub

logger = logging.getLogger(__name__)

STREAMABLE_TYPES = ("video", "audio")


# ─────────────────────────────────────────────────────────────────────────────
#  Access helper
# ─────────────────────────────────────────────────────────────────────────────

async def check_access(user_id: int) -> bool:
    if Config.get("public_bot", False):
        return True
    if user_id in Config.OWNER_ID:
        return True
    return await db.is_sudo_user(str(user_id))


# ─────────────────────────────────────────────────────────────────────────────
#  File upload handler
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(
    (filters.document | filters.video | filters.audio | filters.photo) & filters.private,
    group=0,
)
async def file_handler(client: Client, message: Message):
    user    = message.from_user
    user_id = user.id

    if Config.get("fsub_mode", False):
        if not await check_fsub(client, message):
            return

    if not await check_access(user_id):
        await message.reply(
            f"❌ **{small_caps('access forbidden')}**\n\n"
            "📡 ᴛʜɪꜱ ɪꜱ ᴀ ᴘʀɪᴠᴀᴛᴇ ʙᴏᴛ."
        )
        return

    stats         = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    if Config.get("bandwidth_mode", True) and stats["total_bandwidth"] >= max_bandwidth:
        await message.reply(
            f"❌ **{small_caps('bandwidth limit reached')}!**\n\n"
            "ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀ."
        )
        return

    if message.document:
        file       = message.document
        file_name  = file.file_name or "Document"
        file_size  = file.file_size
        file_type  = file.mime_type.split("/")[0] if file.mime_type else "document"
        tg_file_id = file.file_id
    elif message.video:
        file       = message.video
        file_name  = file.file_name or "Video File"
        file_size  = file.file_size
        file_type  = "video"
        tg_file_id = file.file_id
    elif message.audio:
        file       = message.audio
        file_name  = file.file_name or "Audio File"
        file_size  = file.file_size
        file_type  = "audio"
        tg_file_id = file.file_id
    elif message.photo:
        file       = message.photo
        file_name  = f"{file.file_unique_id}.jpg"
        file_size  = file.file_size
        file_type  = "image"
        tg_file_id = file.file_id
    else:
        await message.reply("❌ ᴜɴꜱᴜᴘᴘᴏʀᴛᴇᴅ ꜰɪʟᴇ ᴛʏᴘᴇ")
        return

    max_file_size = Config.get("max_telegram_size", 4294967296)
    if file_size > max_file_size:
        await message.reply(
            f"❌ **{small_caps('file too large')}**\n\n"
            f"📊 **{small_caps('file size')}:** `{format_size(file_size)}`\n"
            f"⚠️ **{small_caps('max allowed')}:** `{format_size(max_file_size)}`"
        )
        return

    processing_msg = await message.reply("⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʏᴏᴜʀ ꜰɪʟᴇ…")

    try:
        file_info = await client.send_cached_media(
            chat_id=Config.DUMP_CHAT_ID,
            file_id=tg_file_id,
        )
    except Exception as exc:
        logger.error("send_cached_media failed: user=%s err=%s", user_id, exc)
        await processing_msg.edit_text(
            f"❌ **{small_caps('failed to process file')}**\n\n"
            "ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰᴏʀᴡᴀʀᴅ ꜰɪʟᴇ ᴛᴏ ꜱᴛᴏʀᴀɢᴇ.\n"
            f"`{exc}`"
        )
        return

    media = (
        getattr(file_info, "document", None)
        or getattr(file_info, "video",    None)
        or getattr(file_info, "audio",    None)
        or getattr(file_info, "photo",    None)
    )
    if not media:
        logger.error("send_cached_media returned no media: user=%s msg=%s", user_id, file_info.id)
        try:
            await client.delete_messages(Config.DUMP_CHAT_ID, file_info.id)
        except Exception:
            pass
        await processing_msg.edit_text(
            f"❌ **{small_caps('file processing failed')}**\n\n"
            "ꜰɪʟᴇ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ʀᴇᴀᴅ ꜰʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴀꜰᴛᴇʀ ꜰᴏʀᴡᴀʀᴅɪɴɢ."
        )
        return

    file_hash = Cryptic.hash_file_id(str(file_info.id))

    await client.send_message(
        chat_id=Config.DUMP_CHAT_ID,
        text=(
            f"RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ : {user.first_name}\n"
            f"Uꜱᴇʀ ɪᴅ : {user_id}\n"
            f"Fɪʟᴇ ɪᴅ : {file_hash}"
        ),
        reply_to_message_id=file_info.id,
        disable_web_page_preview=True,
    )

    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"

    await db.add_file({
        "file_id":          file_hash,
        "message_id":       str(file_info.id),
        "telegram_file_id": tg_file_id,
        "user_id":          str(user_id),
        "username":         user.username or "",
        "file_name":        file_name,
        "file_size":        file_size,
        "file_type":        file_type,
        "mime_type":        getattr(file, "mime_type", ""),
    })

    is_streamable = file_type in STREAMABLE_TYPES
    buttons       = []

    if is_streamable:
        buttons.append([
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])

    buttons.append([
        InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
        InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
    ])

    safe_name = escape_markdown(file_name)
    fmt_size  = format_size(file_size)

    text = (
        f"✅ **{small_caps('file successfully processed')}!**\n\n"
        f"📂 **{small_caps('file name')}:** `{safe_name}`\n"
        f"💾 **{small_caps('file size')}:** `{fmt_size}`\n"
        f"📊 **{small_caps('file type')}:** `{file_type}`\n"
    )
    if is_streamable:
        text += (
            f"🎬 **{small_caps('streaming')}:** `Available`\n\n"
            f"🔗 **{small_caps('stream link')}:**\n`{stream_link}`"
        )
    else:
        text += f"\n🔗 **{small_caps('download link')}:**\n`{download_link}`"

    await processing_msg.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helper: build file-list buttons
# ─────────────────────────────────────────────────────────────────────────────

def _build_file_buttons(files: list, owner_viewing: bool = False) -> list:
    """Return a list of InlineKeyboardButton rows for a file list."""
    buttons = []
    for f in files[:10]:
        name = f["file_name"]
        if len(name) > 30:
            name = name[:27] + "..."
        mid = f["message_id"]
        if owner_viewing:
            # Embed file owner's user_id so the owner view callback knows
            buttons.append([
                InlineKeyboardButton(
                    f"📄 {name}",
                    callback_data=f"oview_{f['user_id']}_{mid}",
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(f"📄 {name}", callback_data=f"view_{mid}")
            ])
    return buttons


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helper: send files list (with optional Files_IMG)
# ─────────────────────────────────────────────────────────────────────────────

async def _send_files_list(
    client: Client,
    chat_id: int,
    files: list,
    caption: str,
    buttons: list,
    reply_to: int | None = None,
):
    """Send a file list with Files_IMG if configured, else plain text."""
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if Config.Files_IMG:
        try:
            await client.send_photo(
                chat_id=chat_id,
                photo=Config.Files_IMG,
                caption=caption,
                reply_to_message_id=reply_to,
                reply_markup=markup,
            )
            return
        except Exception as exc:
            logger.warning("files list: failed to send photo: %s", exc)

    await client.send_message(
        chat_id=chat_id,
        text=caption,
        reply_to_message_id=reply_to,
        reply_markup=markup,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /files  [user_id]
#
#  No argument  → show the caller's own files (all users).
#  With user_id → owner-only: show that user's files with Files_IMG banner.
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("files") & filters.private, group=0)
async def files_command(client: Client, message: Message):
    caller_id = message.from_user.id

    # ── Owner viewing another user's files ───────────────────────────────────
    if len(message.command) >= 2:
        if caller_id not in Config.OWNER_ID:
            await message.reply(
                "🚫 **Access Denied!**\n\n"
                "🔒 ᴜꜱɪɴɢ `/files <user_id>` ɪꜱ ʀᴇꜱᴛʀɪᴄᴛᴇᴅ ᴛᴏ ʙᴏᴛ ᴏᴡɴᴇʀꜱ."
            )
            return

        target_id = message.command[1]
        if not target_id.lstrip("-").isdigit():
            await message.reply(
                f"❌ **{small_caps('invalid user id')}**\n\n"
                "ᴜꜱᴀɢᴇ: `/files <user_id>`"
            )
            return

        files = await db.get_user_files(target_id, limit=50)

        if not files:
            caption = (
                f"📂 **{small_caps('user files')}**\n\n"
                f"👤 **{small_caps('user id')}:** `{target_id}`\n\n"
                "ᴛʜɪꜱ ᴜꜱᴇʀ ʜᴀꜱ ɴᴏ ꜰɪʟᴇꜱ."
            )
            await _send_files_list(
                client, message.chat.id, [], caption, [], reply_to=message.id
            )
            return

        caption = (
            f"📂 **{small_caps('user files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
            f"👤 **{small_caps('user id')}:** `{target_id}`\n\n"
            "ᴄʟɪᴄᴋ ᴀ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ ᴏʀ ʀᴇᴠᴏᴋᴇ:"
        )
        buttons = _build_file_buttons(files, owner_viewing=True)
        await _send_files_list(
            client, message.chat.id, files, caption, buttons, reply_to=message.id
        )
        return

    # ── Regular user viewing own files ───────────────────────────────────────
    if not await check_access(caller_id):
        await message.reply(f"❌ **{small_caps('access forbidden')}**")
        return

    files = await db.get_user_files(str(caller_id), limit=50)

    if not files:
        caption = (
            f"📂 **{small_caps('your files')}**\n\n"
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ.\n"
            "ꜱᴇɴᴅ ᴍᴇ ᴀ ꜰɪʟᴇ ᴛᴏ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ!"
        )
        await _send_files_list(
            client, message.chat.id, [], caption, [], reply_to=message.id
        )
        return

    caption = (
        f"📂 **{small_caps('your files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
        "ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ:"
    )
    buttons = _build_file_buttons(files, owner_viewing=False)
    await _send_files_list(
        client, message.chat.id, files, caption, buttons, reply_to=message.id
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: view own file details  (view_<message_id>)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^view_\d+$"), group=0)
async def cb_view_file(client: Client, callback: CallbackQuery):
    message_id = callback.data.split("_", 1)[1]
    file_data  = await db.get_file(message_id)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)
        return

    file_hash     = file_data["file_id"]
    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"
    safe_name     = escape_markdown(file_data["file_name"])
    fmt_size      = format_size(file_data["file_size"])

    buttons = [
        [
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
        [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}",     callback_data=f"revoke_{file_hash}")],
        [InlineKeyboardButton(f"⬅️ {small_caps('back')}",       callback_data="back_to_files")],
    ]
    text = (
        f"✅ **{small_caps('file details')}**\n\n"
        f"📂 **{small_caps('name')}:** `{safe_name}`\n"
        f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
        f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
        f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: owner view a specific user's file  (oview_<uid>_<message_id>)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^oview_"), group=0)
async def cb_owner_view_file(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ", show_alert=True)
        return

    # data format: oview_<user_id>_<message_id>
    parts      = callback.data.split("_", 2)
    target_uid = parts[1]
    message_id = parts[2]

    file_data = await db.get_file(message_id)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)
        return

    file_hash     = file_data["file_id"]
    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"
    safe_name     = escape_markdown(file_data["file_name"])
    fmt_size      = format_size(file_data["file_size"])

    buttons = [
        [
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
        [
            InlineKeyboardButton(
                f"🗑️ {small_caps('revoke this file')}",
                callback_data=f"orevoke_{target_uid}_{file_hash}",
            )
        ],
        [
            InlineKeyboardButton(
                f"⬅️ {small_caps('back')}",
                callback_data=f"oback_{target_uid}",
            )
        ],
    ]
    text = (
        f"✅ **{small_caps('file details')}** (owner view)\n\n"
        f"👤 **{small_caps('owner')}:** `{file_data['user_id']}`\n"
        f"📂 **{small_caps('name')}:** `{safe_name}`\n"
        f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
        f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
        f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: owner revoke a specific user's file  (orevoke_<uid>_<hash>)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^orevoke_"), group=0)
async def cb_owner_revoke_file(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ", show_alert=True)
        return

    parts      = callback.data.split("_", 2)
    target_uid = parts[1]
    file_hash  = parts[2]

    file_data = await db.get_file_by_hash(file_hash)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
        return

    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as exc:
        logger.error("orevoke: delete dump msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])
    safe_name = escape_markdown(file_data["file_name"])

    await callback.message.edit_text(
        f"🗑️ **{small_caps('file revoked')}!**\n\n"
        f"📂 **{small_caps('file')}:** `{safe_name}`\n"
        f"👤 **{small_caps('user')}:** `{target_uid}`\n\n"
        "ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ɪɴᴠᴀʟɪᴅᴀᴛᴇᴅ.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"⬅️ {small_caps('back to user files')}",
                callback_data=f"oback_{target_uid}",
            )
        ]]),
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: owner back to user's file list  (oback_<uid>)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^oback_(-?\d+)$"), group=0)
async def cb_owner_back(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ", show_alert=True)
        return

    target_uid = callback.data.split("_", 1)[1]
    files      = await db.get_user_files(target_uid, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 **{small_caps('user files')}**\n\n"
            f"👤 **{small_caps('user id')}:** `{target_uid}`\n\n"
            "ᴛʜɪꜱ ᴜꜱᴇʀ ʜᴀꜱ ɴᴏ ᴍᴏʀᴇ ꜰɪʟᴇꜱ."
        )
        await callback.answer()
        return

    caption = (
        f"📂 **{small_caps('user files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
        f"👤 **{small_caps('user id')}:** `{target_uid}`\n\n"
        "ᴄʟɪᴄᴋ ᴀ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ ᴏʀ ʀᴇᴠᴏᴋᴇ:"
    )
    buttons = _build_file_buttons(files, owner_viewing=True)
    await callback.message.edit_text(
        caption, reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: revoke own file  (revoke_<hash>)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^revoke_[^_]"), group=0)
async def cb_revoke(client: Client, callback: CallbackQuery):
    file_hash = callback.data.split("_", 1)[1]
    file_data = await db.get_file_by_hash(file_hash)

    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
        return

    await db.delete_file(file_data["message_id"])
    safe_name = escape_markdown(file_data["file_name"])

    await callback.message.edit_text(
        f"🗑️ **{small_caps('file revoked successfully')}!**\n\n"
        f"📂 **{small_caps('file')}:** `{safe_name}`\n\n"
        "ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ɪɴᴠᴀʟɪᴅᴀᴛᴇᴅ.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"⬅️ {small_caps('back to files')}",
                callback_data="back_to_files",
            )
        ]]),
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: back to own files  (back_to_files)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^back_to_files$"), group=0)
async def cb_back_to_files(client: Client, callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    files   = await db.get_user_files(user_id, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 **{small_caps('your files')}**\n\n"
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ."
        )
        await callback.answer()
        return

    buttons = _build_file_buttons(files, owner_viewing=False)
    await callback.message.edit_text(
        f"📂 **{small_caps('your files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
        "ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  /stats  (public — accessible to anyone with bot access)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private, group=0)
async def stats_command(client: Client, message: Message):
    user_id = message.from_user.id

    if not await check_access(user_id):
        await message.reply(f"❌ **{small_caps('access forbidden')}**")
        return

    stats = await db.get_stats()
    await message.reply(
        f"📊 **{small_caps('bot statistics')}**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📂 **{small_caps('total files')}:**     `{stats['total_files']}`\n"
        f"👥 **{small_caps('total users')}:**     `{stats['total_users']}`\n\n"
        f"📡 **{small_caps('total bandwidth')}:** `{format_size(stats['total_bandwidth'])}`\n"
        f"📅 **{small_caps('today bandwidth')}:** `{format_size(stats['today_bandwidth'])}`\n"
        f"⬇️ **{small_caps('today downloads')}:** `{stats['today_downloads']}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
