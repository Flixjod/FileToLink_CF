import logging
import math

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
    Message,
)

from config import Config
from helper import Cryptic, format_size, escape_markdown, small_caps, check_fsub
from database import db

logger = logging.getLogger(__name__)

STREAMABLE_TYPES = ("video", "audio")
PAGE_SIZE = 10


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
            disable_web_page_preview=True,
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
            disable_web_page_preview=True,
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
            disable_web_page_preview=True,
        )
        return

    max_file_size = Config.get("max_file_size", 4294967296)
    if file_size > max_file_size:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ **{small_caps('file too large')}**\n\n"
                f"📊 **{small_caps('file size')}:** `{format_size(file_size)}`\n"
                f"⚠️ **{small_caps('max allowed')}:** `{format_size(max_file_size)}`"
            ),
            reply_to_message_id=message.id,
            disable_web_page_preview=True,
        )
        return

    processing_msg = await client.send_message(
        chat_id=message.chat.id,
        text="⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʏᴏᴜʀ ꜰɪʟᴇ…",
        reply_to_message_id=message.id,
        disable_web_page_preview=True,
    )

    try:
        file_info = await client.send_cached_media(
            chat_id=Config.FLOG_CHAT_ID,
            file_id=tg_file_id,
        )
    except Exception as exc:
        logger.error("send_cached_media failed: user=%s err=%s", user_id, exc)
        await processing_msg.edit_text(
            f"❌ **{small_caps('failed to process file')}**\n\n"
            "ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰᴏʀᴡᴀʀᴅ ꜰɪʟᴇ ᴛᴏ ꜱᴛᴏʀᴀɢᴇ.\n"
            f"`{exc}`",
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
            await client.delete_messages(Config.FLOG_CHAT_ID, file_info.id)
        except Exception:
            pass
        await processing_msg.edit_text(
            f"❌ **{small_caps('file processing failed')}**\n\n"
            "ꜰɪʟᴇ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ʀᴇᴀᴅ ꜰʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴀꜰᴛᴇʀ ꜰᴏʀᴡᴀʀᴅɪɴɢ.\n"
            "ᴛʜɪꜱ ᴜꜱᴜᴀʟʟʏ ʜᴀᴘᴘᴇɴꜱ ᴡɪᴛʜ ᴠᴇʀʏ ʟᴀʀɢᴇ ꜰɪʟᴇꜱ. ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ.",
        )
        return

    file_hash = Cryptic.hash_file_id(str(file_info.id))

    await client.send_message(
        chat_id=Config.FLOG_CHAT_ID,
        text=(
            f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ** : [{user.first_name}](tg://user?id={user.id})\n"
            f"**Uꜱᴇʀ ɪᴅ** : `{user_id}`\n"
            f"**Fɪʟᴇ ɪᴅ** : `{file_hash}`"
        ),
        reply_to_message_id=file_info.id,
    )

    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"

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
            InlineKeyboardButton(f"📨 {small_caps('send file')}", callback_data=f"sendfile_{file_hash}"),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=f"file_{file_hash}"),
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
        markup, caption = await _build_user_files_markup(
            client, target_id, page=1, owner_view=True
        )

        if Config.Files_IMG:
            try:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=Config.Files_IMG,
                    caption=caption,
                    reply_to_message_id=message.id,
                    reply_markup=markup,
                )
                return
            except Exception as exc:
                logger.warning("failed to send Files_IMG: %s", exc)

        await client.send_message(
            chat_id=message.chat.id,
            text=caption,
            reply_to_message_id=message.id,
            reply_markup=markup,
        )
        return

    if not await check_access(user_id):
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ **{small_caps('access forbidden')}**",
            reply_to_message_id=message.id,
        )
        return

    markup, caption = await _build_user_files_markup(
        client, str(user_id), page=1, owner_view=False
    )

    if Config.Files_IMG:
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=Config.Files_IMG,
                caption=caption,
                reply_to_message_id=message.id,
                reply_markup=markup,
            )
            return
        except Exception as exc:
            logger.warning("failed to send Files_IMG: %s", exc)

    await client.send_message(
        chat_id=message.chat.id,
        text=caption,
        reply_to_message_id=message.id,
        reply_markup=markup,
    )


async def _build_user_files_markup(
    client,
    user_id: str,
    page: int,
    owner_view: bool,
) -> tuple:
    skip           = (page - 1) * PAGE_SIZE
    user_files_cur, total_files = await db.find_files(user_id, [skip + 1, PAGE_SIZE])

    file_list = []
    async for x in user_files_cur:
        name = x.get("file_name", "Unknown")
        if len(name) > 30:
            name = name[:27] + "…"
        cb = (
            f"ownview_{x['message_id']}_{user_id}"
            if owner_view
            else f"myfile_{x['_id']}_{page}"
        )
        file_list.append([InlineKeyboardButton(f"📄 {name}", callback_data=cb)])

    total_pages = math.ceil(total_files / PAGE_SIZE) if total_files else 1

    if total_files > PAGE_SIZE:
        nav = []
        if page > 1:
            prev_cb = (
                f"ownfiles_{user_id}_{page - 1}"
                if owner_view
                else f"userfiles_{page - 1}"
            )
            nav.append(InlineKeyboardButton("◄", callback_data=prev_cb))
        else:
            nav.append(InlineKeyboardButton("◄", callback_data="N/A"))

        nav.append(InlineKeyboardButton(
            f"{page}/{total_pages}", callback_data="N/A"
        ))

        if page < total_pages:
            next_cb = (
                f"ownfiles_{user_id}_{page + 1}"
                if owner_view
                else f"userfiles_{page + 1}"
            )
            nav.append(InlineKeyboardButton("►", callback_data=next_cb))
        else:
            nav.append(InlineKeyboardButton("►", callback_data="N/A"))

        file_list.append(nav)

    if not file_list or (len(file_list) == 1 and file_list[0][0].callback_data == "N/A"):
        file_list = [[InlineKeyboardButton("ᴇᴍᴘᴛʏ", callback_data="N/A")]]

    file_list.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")])

    markup = InlineKeyboardMarkup(file_list)

    if owner_view:
        caption = (
            f"📂 **{small_caps('files for user')}** `{user_id}`\n"
            f"📊 **{small_caps('total')}:** `{total_files}` "
            f"| **{small_caps('page')}:** `{page}/{total_pages}`\n\n"
            "ᴄʟɪᴄᴋ ᴀ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴏʀ ʀᴇᴠᴏᴋᴇ ɪᴛ:"
        ) if total_files else (
            f"📂 **{small_caps('files for user')}** `{user_id}`\n\n"
            "ᴛʜɪꜱ ᴜꜱᴇʀ ʜᴀꜱ ɴᴏ ꜰɪʟᴇꜱ ʏᴇᴛ."
        )
    else:
        caption = (
            f"📂 **{small_caps('your files')}**\n"
            f"📊 **{small_caps('total')}:** `{total_files}` "
            f"| **{small_caps('page')}:** `{page}/{total_pages}`\n\n"
            "ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟꜱ:"
        ) if total_files else (
            f"📂 **{small_caps('your files')}**\n\n"
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ. "
            "ꜱᴇɴᴅ ᴍᴇ ᴀ ꜰɪʟᴇ ᴛᴏ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ!"
        )

    return markup, caption


# Unified file & navigation callback handler
@Client.on_callback_query(
    filters.regex(
        r"^(userfiles_|ownfiles_|myfile_|ownview_|ownrevoke_|ownback_|view_|revoke_|"
        r"revoke_confirm_|revoke_cancel_|ownrevoke_confirm_|ownrevoke_cancel_|"
        r"sendfile_|back_to_files|close).*"
    ),
    group=0,
)
async def file_callback_handler(client: Client, callback: CallbackQuery):
    data    = callback.data
    user_id = callback.from_user.id

    # Paginate: user's own files
    if data.startswith("userfiles_"):
        page   = int(data.replace("userfiles_", ""))
        markup, caption = await _build_user_files_markup(
            client, str(user_id), page=page, owner_view=False
        )
        try:
            await callback.message.edit_text(caption, reply_markup=markup)
        except Exception:
            pass
        return await callback.answer()

    # Paginate: owner viewing a target user's files
    if data.startswith("ownfiles_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        parts     = data.split("_", 2)
        target_id = parts[1]
        page      = int(parts[2]) if len(parts) > 2 else 1
        markup, caption = await _build_user_files_markup(
            client, target_id, page=page, owner_view=True
        )
        try:
            await callback.message.edit_text(caption, reply_markup=markup)
        except Exception:
            pass
        return await callback.answer()

    # User clicks a file from their paginated list
    if data.startswith("myfile_"):
        parts     = data.split("_", 2)
        oid_str   = parts[1]
        back_page = int(parts[2]) if len(parts) > 2 else 1

        from bson import ObjectId
        try:
            file_data = await db.files.find_one({"_id": ObjectId(oid_str)})
        except Exception:
            file_data = None

        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)

        file_hash     = file_data["file_id"]
        base_url      = Config.URL or f"http://localhost:{Config.PORT}"
        stream_link   = f"{base_url}/stream/{file_hash}"
        download_link = f"{base_url}/dl/{file_hash}"
        safe_name     = escape_markdown(file_data["file_name"])
        fmt_size      = format_size(file_data["file_size"])

        buttons = [
            [
                InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
            ],
            [
                InlineKeyboardButton(f"📨 {small_caps('send file')}", callback_data=f"sendfile_{file_hash}"),
                InlineKeyboardButton(f"🔁 {small_caps('share')}",     switch_inline_query=f"file_{file_hash}"),
            ],
            [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}",  callback_data=f"revoke_{file_hash}")],
            [InlineKeyboardButton(f"⬅️ {small_caps('back')}",    callback_data=f"userfiles_{back_page}")],
        ]
        text = (
            f"✅ **{small_caps('file details')}**\n\n"
            f"📂 **{small_caps('name')}:** `{safe_name}`\n"
            f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
            f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
            f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
        )
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return await callback.answer()

    # Owner: view file detail
    if data.startswith("ownview_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        parts      = data.split("_", 2)
        message_id = parts[1]
        target_id  = parts[2] if len(parts) > 2 else ""

        file_data = await db.get_file(message_id)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)

        file_hash     = file_data["file_id"]
        base_url      = Config.URL or f"http://localhost:{Config.PORT}"
        stream_link   = f"{base_url}/stream/{file_hash}"
        download_link = f"{base_url}/dl/{file_hash}"
        telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start=file_{file_hash}"
        safe_name     = escape_markdown(file_data["file_name"])
        fmt_size      = format_size(file_data["file_size"])

        buttons = [
            [
                InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
            ],
            [InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link)],
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
            f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
            f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
            f"👤 **{small_caps('owner')}:** `{file_data.get('user_id', 'N/A')}`\n"
            f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
        )
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return await callback.answer()

    # Owner: revoke file — show confirmation first
    if data.startswith("ownrevoke_") and not data.startswith("ownrevoke_confirm_") and not data.startswith("ownrevoke_cancel_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        parts     = data.split("_", 2)
        file_hash = parts[1]
        target_id = parts[2] if len(parts) > 2 else ""

        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)

        safe_name = escape_markdown(file_data["file_name"])
        await callback.message.edit_text(
            f"**Cᴏɴғɪʀᴍ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜᴇ Fɪʟᴇ**\n\n"
            f"📂 `{safe_name}`",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ʏᴇs", callback_data=f"ownrevoke_confirm_{file_hash}_{target_id}"),
                    InlineKeyboardButton("ɴᴏ",  callback_data=f"ownrevoke_cancel_{target_id}"),
                ]
            ]),
        )
        return await callback.answer()

    # Owner: confirmed revoke
    if data.startswith("ownrevoke_confirm_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        rest      = data[len("ownrevoke_confirm_"):]
        parts     = rest.split("_", 1)
        file_hash = parts[0]
        target_id = parts[1] if len(parts) > 1 else ""

        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)

        try:
            await client.delete_messages(Config.FLOG_CHAT_ID, int(file_data["message_id"]))
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
                    callback_data=f"ownfiles_{target_id}_1",
                )],
            ]),
        )
        return await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)

    # Owner: cancelled revoke — go back to file view
    if data.startswith("ownrevoke_cancel_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        target_id = data[len("ownrevoke_cancel_"):]
        markup, caption = await _build_user_files_markup(
            client, target_id, page=1, owner_view=True
        )
        try:
            await callback.message.edit_text(caption, reply_markup=markup)
        except Exception:
            pass
        return await callback.answer("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.", show_alert=False)

    # Owner: back to user files list
    if data.startswith("ownback_"):
        if user_id not in Config.OWNER_ID:
            return await callback.answer("🚫 Owner only.", show_alert=True)
        target_id = data.replace("ownback_", "", 1)
        markup, caption = await _build_user_files_markup(
            client, target_id, page=1, owner_view=True
        )
        try:
            await callback.message.edit_text(caption, reply_markup=markup)
        except Exception:
            pass
        return await callback.answer()

    # User: view own file detail (legacy view_ prefix)
    if data.startswith("view_"):
        message_id = data.replace("view_", "", 1)
        file_data  = await db.get_file(message_id)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)

        file_hash     = file_data["file_id"]
        base_url      = Config.URL or f"http://localhost:{Config.PORT}"
        stream_link   = f"{base_url}/stream/{file_hash}"
        download_link = f"{base_url}/dl/{file_hash}"
        safe_name     = escape_markdown(file_data["file_name"])
        fmt_size      = format_size(file_data["file_size"])

        buttons = [
            [
                InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
                InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
            ],
            [
                InlineKeyboardButton(f"📨 {small_caps('send file')}", callback_data=f"sendfile_{file_hash}"),
                InlineKeyboardButton(f"🔁 {small_caps('share')}",     switch_inline_query=f"file_{file_hash}"),
            ],
            [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}",  callback_data=f"revoke_{file_hash}")],
            [InlineKeyboardButton(f"⬅️ {small_caps('back')}",    callback_data="back_to_files")],
        ]
        text = (
            f"✅ **{small_caps('file details')}**\n\n"
            f"📂 **{small_caps('name')}:** `{safe_name}`\n"
            f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
            f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
            f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
        )
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return await callback.answer()

    # User: revoke own file — show confirmation first
    if data.startswith("revoke_") and not data.startswith("revoke_confirm_") and not data.startswith("revoke_cancel_"):
        file_hash = data.replace("revoke_", "", 1)
        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)

        safe_name = escape_markdown(file_data["file_name"])
        await callback.message.edit_text(
            f"**Cᴏɴғɪʀᴍ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜᴇ Fɪʟᴇ**\n\n"
            f"📂 `{safe_name}`",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ʏᴇs", callback_data=f"revoke_confirm_{file_hash}"),
                    InlineKeyboardButton("ɴᴏ",  callback_data=f"revoke_cancel_{file_hash}"),
                ]
            ]),
        )
        return await callback.answer()

    # User: confirmed revoke
    if data.startswith("revoke_confirm_"):
        file_hash = data[len("revoke_confirm_"):]
        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)

        await db.delete_file(file_data["message_id"])
        safe_name = escape_markdown(file_data["file_name"])
        await callback.message.edit_text(
            f"🗑️ **{small_caps('file revoked successfully')}!**\n\n"
            f"📂 **{small_caps('file')}:** `{safe_name}`\n\n"
            "ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ɪɴᴠᴀʟɪᴅᴀᴛᴇᴅ.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⬅️ {small_caps('back to files')}", callback_data="userfiles_1")],
            ]),
        )
        return await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)

    # User: cancelled revoke — go back to file detail
    if data.startswith("revoke_cancel_"):
        file_hash = data[len("revoke_cancel_"):]
        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ", show_alert=True)

        from bson import ObjectId
        file_doc = await db.files.find_one({"file_id": file_hash})
        back_page = 1
        if file_doc:
            oid_str = str(file_doc["_id"])
            markup, caption = await _build_user_files_markup(
                client, str(user_id), page=back_page, owner_view=False
            )
            base_url      = Config.URL or f"http://localhost:{Config.PORT}"
            stream_link   = f"{base_url}/stream/{file_hash}"
            download_link = f"{base_url}/dl/{file_hash}"
            safe_name     = escape_markdown(file_data["file_name"])
            fmt_size      = format_size(file_data["file_size"])
            buttons = [
                [
                    InlineKeyboardButton(f"🌐 {small_caps('stream')}",   url=stream_link),
                    InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
                ],
                [
                    InlineKeyboardButton(f"📨 {small_caps('send file')}", callback_data=f"sendfile_{file_hash}"),
                    InlineKeyboardButton(f"🔁 {small_caps('share')}",     switch_inline_query=f"file_{file_hash}"),
                ],
                [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}",  callback_data=f"revoke_{file_hash}")],
                [InlineKeyboardButton(f"⬅️ {small_caps('back')}",    callback_data=f"userfiles_{back_page}")],
            ]
            text = (
                f"✅ **{small_caps('file details')}**\n\n"
                f"📂 **{small_caps('name')}:** `{safe_name}`\n"
                f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
                f"📊 **{small_caps('type')}:** `{file_data['file_type']}`\n"
                f"📅 **{small_caps('uploaded')}:** `{file_data['created_at'].strftime('%Y-%m-%d')}`"
            )
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return await callback.answer("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.", show_alert=False)

    # User: back to own files list
    if data == "back_to_files":
        markup, caption = await _build_user_files_markup(
            client, str(user_id), page=1, owner_view=False
        )
        try:
            await callback.message.edit_text(caption, reply_markup=markup)
        except Exception:
            pass
        return await callback.answer()

    # Send file to user
    if data.startswith("sendfile_"):
        file_hash = data.replace("sendfile_", "", 1)
        file_data = await db.get_file_by_hash(file_hash)
        if not file_data:
            return await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ʜᴀꜱ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)

        await callback.answer("📨 ꜱᴇɴᴅɪɴɢ ꜰɪʟᴇ…", show_alert=False)
        try:
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=Config.FLOG_CHAT_ID,
                message_id=int(file_data["message_id"]),
            )
        except Exception as exc:
            logger.error("sendfile copy_message failed: user=%s hash=%s err=%s", user_id, file_hash, exc)
            try:
                await client.send_message(
                    chat_id=user_id,
                    text=f"❌ **{small_caps('could not send file')}**\n\n`{exc}`",
                )
            except Exception:
                pass
        return

    # Close / dismiss
    if data == "close":
        try:
            await callback.message.delete()
        except Exception:
            pass
        return await callback.answer()


@Client.on_inline_query(group=0)
async def inline_query_handler(client: Client, inline_query):
    query = (inline_query.query or "").strip()
    if not query:
        await inline_query.answer(
            results=[],
            cache_time=1,
            switch_pm_text="ꜱᴇɴᴅ ᴀ ꜰɪʟᴇ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ʟɪɴᴋ",
            switch_pm_parameter="start",
        )
        return

    # Strip the "file_" prefix that the Share button injects
    file_hash_query = query[5:] if query.startswith("file_") else query

    file_data = await db.get_file_by_hash(file_hash_query)
    if not file_data:
        await inline_query.answer(
            results=[],
            cache_time=5,
            switch_pm_text="❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ",
            switch_pm_parameter="start",
        )
        return

    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    file_hash     = file_data["file_id"]
    stream_link   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start=file_{file_hash}"
    file_type     = file_data.get("file_type", "document")
    is_streamable = file_type in STREAMABLE_TYPES
    safe_name     = escape_markdown(file_data["file_name"])
    fmt_size      = format_size(file_data["file_size"])
    tg_file_id    = file_data.get("telegram_file_id", "")

    text = (
        f"📂 **{small_caps('file')}:** `{safe_name}`\n"
        f"💾 **{small_caps('size')}:** `{fmt_size}`\n"
        f"📊 **{small_caps('type')}:** `{file_type}`\n\n"
    )
    if is_streamable:
        text += f"🎬 **{small_caps('stream')}:** {stream_link}\n"
    text += f"📥 **{small_caps('download')}:** {download_link}"

    btn_rows = []
    if is_streamable:
        btn_rows.append([
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])
    else:
        btn_rows.append([
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ])
    btn_rows.append([
        InlineKeyboardButton(f"📩 {small_caps('get file via bot')}", url=telegram_link),
    ])
    markup = InlineKeyboardMarkup(btn_rows)

    THUMB_VIDEO    = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Clapper%20board/3D/clapper_board_3d.png"
    THUMB_AUDIO    = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Musical%20note/3D/musical_note_3d.png"
    THUMB_IMAGE    = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Framed%20picture/3D/framed_picture_3d.png"
    THUMB_DOCUMENT = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Page%20facing%20up/3D/page_facing_up_3d.png"
    DEFAULT_THUMB  = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/File%20folder/3D/file_folder_3d.png"

    TYPE_THUMBS = {
        "video":    THUMB_VIDEO,
        "audio":    THUMB_AUDIO,
        "image":    THUMB_IMAGE,
        "document": THUMB_DOCUMENT,
    }
    thumb_url = TYPE_THUMBS.get(file_type, DEFAULT_THUMB)

    result_item = None

    if file_type == "image" and tg_file_id:
        try:
            result_item = InlineQueryResultPhoto(
                photo_url=stream_link,
                thumb_url=stream_link,
                title=f"{file_data['file_name']}",
                description=small_caps(f"image • {fmt_size}"),
                caption=text,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        except Exception as exc:
            logger.debug("InlineQueryResultPhoto build failed: %s", exc)

    if result_item is None:
        result_item = InlineQueryResultArticle(
            title=f"{file_data['file_name']}",
            description=small_caps(f"{file_type} • {fmt_size}"),
            input_message_content=InputTextMessageContent(
                message_text=text,
                disable_web_page_preview=True,
            ),
            reply_markup=markup,
            thumb_url=thumb_url,
            thumb_width=64,
            thumb_height=64,
        )

    await inline_query.answer(results=[result_item], cache_time=30)
