import logging

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from helper import Cryptic, format_size, escape_markdown, small_caps, check_fsub
from database import db

logger = logging.getLogger(__name__)

STREAMABLE_TYPES = ("video", "audio")


async def check_access(user_id: int) -> bool:
    if Config.get("public_bot", False):
        return True
    if user_id in Config.OWNER_ID:
        return True
    return await db.is_sudo_user(str(user_id))


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
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ **{small_caps('access forbidden')}**\n\n📡 ᴛʜɪꜱ ɪꜱ ᴀ ᴘʀɪᴠᴀᴛᴇ ʙᴏᴛ.",
            reply_to_message_id=message.id,
        )
        return

    stats         = await db.get_bandwidth_stats()
    max_bandwidth = Config.get("max_bandwidth", 107374182400)
    if Config.get("bandwidth_mode", True) and stats["total_bandwidth"] >= max_bandwidth:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ **{small_caps('bandwidth limit reached')}!**\n\n"
                "ᴘʟᴇᴀꜱᴇ ᴄᴏɴᴛᴀᴄᴛ ᴛʜᴇ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴛᴏʀ."
            ),
            reply_to_message_id=message.id,
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
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ᴜɴꜱᴜᴘᴘᴏʀᴛᴇᴅ ꜰɪʟᴇ ᴛʏᴘᴇ",
            reply_to_message_id=message.id,
        )
        return

    max_file_size = Config.get("max_telegram_size", 4294967296)
    if file_size > max_file_size:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ **{small_caps('file too large')}**\n\n"
                f"📊 **{small_caps('file size')}:** `{format_size(file_size)}`\n"
                f"⚠️ **{small_caps('max allowed')}:** `{format_size(max_file_size)}`"
            ),
            reply_to_message_id=message.id,
        )
        return

    processing_msg = await client.send_message(
        chat_id=message.chat.id,
        text="⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʏᴏᴜʀ ꜰɪʟᴇ…",
        reply_to_message_id=message.id,
    )

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
            "ꜰɪʟᴇ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ʀᴇᴀᴅ ꜰʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴀꜰᴛᴇʀ ꜰᴏʀᴡᴀʀᴅɪɴɢ.\n"
            "ᴛʜɪꜱ ᴜꜱᴜᴀʟʟʏ ʜᴀᴘᴘᴇɴꜱ ᴡɪᴛʜ ᴠᴇʀʏ ʟᴀʀɢᴇ ꜰɪʟᴇꜱ. ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ."
        )
        return

    file_hash = Cryptic.hash_file_id(str(file_info.id))

    await client.send_message(
        chat_id=Config.DUMP_CHAT_ID,
        text=(
            f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ** : [{user.first_name}](tg://user?id={user.id})\n"
            f"**Uꜱᴇʀ ɪᴅ** : `{user_id}`\n"
            f"**Fɪʟᴇ ɪᴅ** : `{file_hash}`"
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
            InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])

    buttons.extend([
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
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
            f"🌐 **{small_caps('streaming')}:** `Available`\n\n"
            f"🔗 **{small_caps('stream link')}:**\n`{stream_link}`"
        )
    else:
        text += f"\n🔗 **{small_caps('download link')}:**\n`{download_link}`"

    await processing_msg.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_message(filters.command("files") & filters.private, group=0)
async def files_command(client: Client, message: Message):
    user_id = message.from_user.id

    # ── Owner: /files <target_user_id> ──────────────────────────────────
    if len(message.command) > 1:
        if user_id not in Config.OWNER_ID:
            await client.send_message(
                chat_id=message.chat.id,
                text="🚫 **Access Denied!**\n\n🔒 Only the bot owner can view other users' files.",
                reply_to_message_id=message.id,
            )
            return

        raw = message.command[1]
        if not raw.lstrip("-").isdigit():
            await client.send_message(
                chat_id=message.chat.id,
                text=(
                    f"❌ **{small_caps('invalid user id')}**\n\n"
                    "ᴜꜱᴀɢᴇ: `/files <user_id>`"
                ),
                reply_to_message_id=message.id,
            )
            return

        target_id = raw
        files     = await db.get_user_files(target_id, limit=50)

        empty_caption = (
            f"📂 **{small_caps('files for user')}** `{target_id}`\n\n"
            "ᴛʜɪꜱ ᴜꜱᴇʀ ʜᴀꜱ ɴᴏ ꜰɪʟᴇꜱ ʏᴇᴛ."
        )

        if not files:
            if Config.Files_IMG:
                try:
                    await client.send_photo(
                        chat_id=message.chat.id,
                        photo=Config.Files_IMG,
                        caption=empty_caption,
                        reply_to_message_id=message.id,
                    )
                    return
                except Exception as exc:
                    logger.warning("failed to send Files_IMG: %s", exc)
            await client.send_message(
                chat_id=message.chat.id,
                text=empty_caption,
                reply_to_message_id=message.id,
            )
            return

        buttons = []
        for f in files[:10]:
            name = f["file_name"]
            if len(name) > 30:
                name = name[:27] + "..."
            buttons.append([
                InlineKeyboardButton(
                    f"📄 {name}",
                    callback_data=f"ownview_{f['message_id']}_{target_id}",
                )
            ])

        list_caption = (
            f"📂 **{small_caps('files for user')}** `{target_id}`"
            f" (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
            "ᴄʟɪᴄᴋ ᴀ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴏʀ ʀᴇᴠᴏᴋᴇ ɪᴛ:"
        )

        if Config.Files_IMG:
            try:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=Config.Files_IMG,
                    caption=list_caption,
                    reply_to_message_id=message.id,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            except Exception as exc:
                logger.warning("failed to send Files_IMG: %s", exc)

        await client.send_message(
            chat_id=message.chat.id,
            text=list_caption,
            reply_to_message_id=message.id,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # ── Normal user: own files ───────────────────────────────────────────
    if not await check_access(user_id):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ **{small_caps('access forbidden')}**",
            reply_to_message_id=message.id,
        )
        return

    files = await db.get_user_files(str(user_id), limit=50)

    empty_text = (
        f"📂 **{small_caps('your files')}**\n\n"
        "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ. "
        "ꜱᴇɴᴅ ᴍᴇ ᴀ ꜰɪʟᴇ ᴛᴏ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ!"
    )

    if not files:
        if Config.Files_IMG:
            try:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=Config.Files_IMG,
                    caption=empty_text,
                    reply_to_message_id=message.id,
                )
                return
            except Exception as exc:
                logger.warning("failed to send Files_IMG: %s", exc)
        await client.send_message(
            chat_id=message.chat.id,
            text=empty_text,
            reply_to_message_id=message.id,
        )
        return

    buttons = []
    for f in files[:10]:
        name = f["file_name"]
        if len(name) > 30:
            name = name[:27] + "..."
        buttons.append([
            InlineKeyboardButton(f"📄 {name}", callback_data=f"view_{f['message_id']}")
        ])

    final_text = (
        f"📂 **{small_caps('your files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\n"
        "ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ:"
    )

    if Config.Files_IMG:
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=Config.Files_IMG,
                caption=final_text,
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return
        except Exception as exc:
            logger.warning("failed to send Files_IMG: %s", exc)

    await client.send_message(
        chat_id=message.chat.id,
        text=final_text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── Owner: view file detail (with delete option) ─────────────────────────────
@Client.on_callback_query(filters.regex(r"^ownview_"), group=0)
async def cb_owner_view_file(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 Owner only.", show_alert=True)
        return

    # callback_data format: ownview_<message_id>_<target_user_id>
    parts      = callback.data.split("_", 2)
    message_id = parts[1]
    target_id  = parts[2] if len(parts) > 2 else ""

    file_data = await db.get_file(message_id)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)
        return

    file_hash     = file_data["file_id"]
    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"

    safe_name      = escape_markdown(file_data["file_name"])
    formatted_size = format_size(file_data["file_size"])

    buttons = [
        [
            InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
        ],
        [InlineKeyboardButton(
            f"🗑️ {small_caps('revoke this file')}",
            callback_data=f"ownrevoke_{file_hash}_{target_id}",
        )],
        [InlineKeyboardButton(
            f"⬅️ {small_caps('back')}",
            callback_data=f"ownback_{target_id}",
        )],
    ]
    text = (
        f"✅ **{small_caps('file details')}** *(owner view)*\n\n"
        f"📂 **{small_caps('name')}:** `{safe_name}`\n"
        f"💾 **{small_caps('size')}:** `{formatted_size}`\n"
        f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
        f"👤 **{small_caps('owner')}:** `{file_data.get('user_id', 'N/A')}`\n"
        f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


# ── Owner: revoke a specific file ────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^ownrevoke_"), group=0)
async def cb_owner_revoke_file(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 Owner only.", show_alert=True)
        return

    # callback_data format: ownrevoke_<file_hash>_<target_user_id>
    parts     = callback.data.split("_", 2)
    file_hash = parts[1]
    target_id = parts[2] if len(parts) > 2 else ""

    file_data = await db.get_file_by_hash(file_hash)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
        return

    # Delete from dump channel
    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as exc:
        logger.error("owner revoke dump delete: msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])

    safe_name = escape_markdown(file_data["file_name"])
    await callback.message.edit_text(
        f"🗑️ **{small_caps('file revoked successfully')}!**\n\n"
        f"📂 **{small_caps('file')}:** `{safe_name}`\n\n"
        "ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ɪɴᴠᴀʟɪᴅᴀᴛᴇᴅ.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"⬅️ {small_caps('back to user files')}",
                callback_data=f"ownback_{target_id}",
            )],
        ]),
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


# ── Owner: back to user files list ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^ownback_"), group=0)
async def cb_owner_back(client: Client, callback: CallbackQuery):
    if callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("🚫 Owner only.", show_alert=True)
        return

    target_id = callback.data.replace("ownback_", "", 1)
    files     = await db.get_user_files(target_id, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 **{small_caps('files for user')}** `{target_id}`\n\n"
            "ᴛʜɪꜱ ᴜꜱᴇʀ ʜᴀꜱ ɴᴏ ꜰɪʟᴇꜱ ʏᴇᴛ."
        )
        await callback.answer()
        return

    buttons = []
    for f in files[:10]:
        name = f["file_name"]
        if len(name) > 30:
            name = name[:27] + "..."
        buttons.append([
            InlineKeyboardButton(
                f"📄 {name}",
                callback_data=f"ownview_{f['message_id']}_{target_id}",
            )
        ])

    await callback.message.edit_text(
        f"📂 **{small_caps('files for user')}** `{target_id}`"
        f" (`{len(files)}` ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴀ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴏʀ ʀᴇᴠᴏᴋᴇ ɪᴛ:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await callback.answer()


# ── User: view own file detail ────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^view_"), group=0)
async def cb_view_file(client: Client, callback: CallbackQuery):
    message_id = callback.data.replace("view_", "", 1)
    file_data  = await db.get_file(message_id)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)
        return

    file_hash     = file_data["file_id"]
    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"

    safe_name      = escape_markdown(file_data["file_name"])
    formatted_size = format_size(file_data["file_size"])

    buttons = [
        [
            InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
        [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}",  callback_data=f"revoke_{file_hash}")],
        [InlineKeyboardButton(f"⬅️ {small_caps('back')}",    callback_data="back_to_files")],
    ]
    text = (
        f"✅ **{small_caps('file details')}**\n\n"
        f"📂 **{small_caps('name')}:** `{safe_name}`\n"
        f"💾 **{small_caps('size')}:** `{formatted_size}`\n"
        f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
        f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


# ── User: revoke own file ─────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^revoke_"), group=0)
async def cb_revoke(client: Client, callback: CallbackQuery):
    file_hash = callback.data.replace("revoke_", "", 1)

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
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬅️ {small_caps('back to files')}", callback_data="back_to_files")],
        ]),
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


# ── User: back to own files list ──────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^back_to_files$"), group=0)
async def cb_back_to_files(client: Client, callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    files   = await db.get_user_files(user_id, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 **{small_caps('your files')}**\n\nʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ."
        )
        await callback.answer()
        return

    buttons = []
    for f in files[:10]:
        name = f["file_name"]
        if len(name) > 30:
            name = name[:27] + "..."
        buttons.append([
            InlineKeyboardButton(f"📄 {name}", callback_data=f"view_{f['message_id']}")
        ])

    await callback.message.edit_text(
        f"📂 **{small_caps('your files')}** (`{len(files)}` ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await callback.answer()

