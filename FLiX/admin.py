import logging

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from config import Config
from helper import small_caps, format_size, escape_markdown

logger = logging.getLogger(__name__)


def _is_owner(_, __, message: Message) -> bool:
    result = message.from_user.id in Config.OWNER_ID
    if not result:
        logger.warning(
            "unauthorized admin attempt | user=%s cmd=%s",
            message.from_user.id,
            getattr(message, "command", ["?"])[0] if message.command else "?",
        )
    return result


owner = filters.create(_is_owner)


# ══════════════════════════════════════════════════════════════════════════
#  ADMIN MESSAGE HANDLERS
# ══════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("setpublic") & filters.private & owner, group=2)
async def setpublic_command(client: Client, message: Message):
    from database import db

    user_id   = message.from_user.id
    logger.info("/setpublic | owner=%s", user_id)
    current   = Config.get("public_bot", False)
    new_value = not current
    await Config.update(db.db, {"public_bot": new_value})
    mode = "ᴘᴜʙʟɪᴄ" if new_value else "ᴘʀɪᴠᴀᴛᴇ"
    logger.info("public_bot → %s | owner=%s", new_value, user_id)
    await message.reply_text(
        f"✅ ʙᴏᴛ ᴍᴏᴅᴇ sᴇᴛ ᴛᴏ: *{mode}*",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("addsudo") & filters.private & owner, group=2)
async def addsudo_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/addsudo | owner=%s args=%s", user_id, message.command)
    if len(message.command) < 2:
        await message.reply_text(
            "❌ ᴜsᴀɢᴇ: `/addsudo <user_id>`",
            reply_to_message_id=message.id,
        )
        return
    try:
        target = message.command[1]
        await db.add_sudo_user(target, str(user_id))
        logger.info("sudo granted | target=%s by=%s", target, user_id)
        await message.reply_text(
            f"✅ ᴜsᴇʀ `{target}` ᴀᴅᴅᴇᴅ ᴀs sᴜᴅᴏ",
            reply_to_message_id=message.id,
        )
    except Exception as exc:
        logger.error("addsudo error | owner=%s err=%s", user_id, exc)
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {exc}", reply_to_message_id=message.id)


@Client.on_message(filters.command("rmsudo") & filters.private & owner, group=2)
async def rmsudo_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/rmsudo | owner=%s args=%s", user_id, message.command)
    if len(message.command) < 2:
        await message.reply_text(
            "❌ ᴜsᴀɢᴇ: `/rmsudo <user_id>`",
            reply_to_message_id=message.id,
        )
        return
    try:
        target = message.command[1]
        result = await db.remove_sudo_user(target)
        if result:
            logger.info("sudo revoked | target=%s by=%s", target, user_id)
            await message.reply_text(
                f"✅ ᴜsᴇʀ `{target}` ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ sᴜᴅᴏ",
                reply_to_message_id=message.id,
            )
        else:
            await message.reply_text(
                f"❌ ᴜsᴇʀ `{target}` ɴᴏᴛ ғᴏᴜɴᴅ",
                reply_to_message_id=message.id,
            )
    except Exception as exc:
        logger.error("rmsudo error | owner=%s err=%s", user_id, exc)
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {exc}", reply_to_message_id=message.id)


@Client.on_message(filters.command("sudolist") & filters.private & owner, group=2)
async def sudolist_command(client: Client, message: Message):
    from database import db

    logger.info("/sudolist | owner=%s", message.from_user.id)
    sudo_users = await db.get_sudo_users()
    if not sudo_users:
        await message.reply_text(
            f"📋 *{small_caps('sudo users')}*\n\nɴᴏ sᴜᴅᴏ ᴜsᴇʀs ғᴏᴜɴᴅ.",
            reply_to_message_id=message.id,
        )
        return
    text = f"📋 *{small_caps('sudo users')}* ({len(sudo_users)})\n\n"
    for u in sudo_users:
        text += f"• `{u['user_id']}`\n"
    await message.reply_text(text, reply_to_message_id=message.id)


@Client.on_message(filters.command("setbandwidth") & filters.private & owner, group=2)
async def setbandwidth_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/setbandwidth | owner=%s args=%s", user_id, message.command)
    if len(message.command) < 2:
        await message.reply_text(
            "❌ ᴜsᴀɢᴇ: `/setbandwidth <bytes>`\n\n"
            "ᴇxᴀᴍᴘʟᴇs:\n"
            "`/setbandwidth 107374182400` (100GB)\n"
            "`/setbandwidth 53687091200`  (50GB)",
            reply_to_message_id=message.id,
        )
        return
    try:
        new_limit = int(message.command[1])
        await Config.update(db.db, {"max_bandwidth": new_limit})
        logger.info("bandwidth limit → %s | owner=%s", new_limit, user_id)
        await message.reply_text(
            f"✅ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ sᴇᴛ ᴛᴏ: `{format_size(new_limit)}`",
            reply_to_message_id=message.id,
        )
    except ValueError as exc:
        logger.error("setbandwidth invalid value | owner=%s err=%s", user_id, exc)
        await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ғᴏʀᴍᴀᴛ", reply_to_message_id=message.id)


@Client.on_message(filters.command("setfsub") & filters.private & owner, group=2)
async def setfsub_command(client: Client, message: Message):
    from database import db

    user_id   = message.from_user.id
    logger.info("/setfsub | owner=%s", user_id)
    current   = Config.get("fsub_mode", False)
    new_value = not current
    await Config.update(db.db, {"fsub_mode": new_value})
    status = "ᴇɴᴀʙʟᴇᴅ" if new_value else "ᴅɪsᴀʙʟᴇᴅ"
    logger.info("fsub_mode → %s | owner=%s", new_value, user_id)
    await message.reply_text(
        f"✅ ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ: *{status}*",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("broadcast") & filters.private & owner, group=2)
async def broadcast_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/broadcast | owner=%s", user_id)
    if not message.reply_to_message:
        await message.reply_text(
            f"❌ *{small_caps('usage')}:*\n\nʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ `/broadcast`",
            reply_to_message_id=message.id,
        )
        return

    users = await db.users.find({}).to_list(length=None)
    if not users:
        await message.reply_text("❌ ɴᴏ ᴜsᴇʀs ғᴏᴜɴᴅ", reply_to_message_id=message.id)
        return

    status_msg = await message.reply_text(
        f"📢 sᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ {len(users)} ᴜsᴇʀs...",
        reply_to_message_id=message.id,
    )
    success = failed = 0
    for user in users:
        try:
            await message.reply_to_message.copy(chat_id=int(user["user_id"]))
            success += 1
        except Exception as exc:
            logger.error("broadcast failed | target=%s err=%s", user["user_id"], exc)
            failed += 1

    logger.info("broadcast done | sent=%s failed=%s owner=%s", success, failed, user_id)
    await status_msg.edit_text(
        f"✅ *{small_caps('broadcast completed')}*\n\n"
        f"📤 *{small_caps('sent')}:* {success}\n"
        f"❌ *{small_caps('failed')}:* {failed}"
    )


@Client.on_message(filters.command("revokeall") & filters.private & owner, group=2)
async def revokeall_command(client: Client, message: Message):
    from database import db

    logger.info("/revokeall | owner=%s", message.from_user.id)
    stats       = await db.get_stats()
    total_files = stats["total_files"]
    if total_files == 0:
        await message.reply_text("📂 ɴᴏ ғɪʟᴇs ᴛᴏ ᴅᴇʟᴇᴛᴇ.", reply_to_message_id=message.id)
        return
    await message.reply_text(
        f"⚠️ *{small_caps('warning')}*\n\n"
        f"ᴛʜɪs ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ *{total_files}* ғɪʟᴇs.\n"
        f"sᴇɴᴅ `/confirmdelete` ᴛᴏ ᴄᴏɴғɪʀᴍ.",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("confirmdelete") & filters.private & owner, group=2)
async def confirmdelete_command(client: Client, message: Message):
    from database import db

    user_id = message.from_user.id
    logger.info("/confirmdelete | owner=%s", user_id)
    msg = await message.reply_text("🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ғɪʟᴇs...", reply_to_message_id=message.id)
    deleted_count = await db.delete_all_files()
    logger.info("all files deleted | count=%s owner=%s", deleted_count, user_id)
    await msg.edit_text(
        f"🗑️ *{small_caps('all files deleted')}!*\n\nᴅᴇʟᴇᴛᴇᴅ {deleted_count} ғɪʟᴇs."
    )


@Client.on_message(filters.command("logs") & filters.private & owner, group=2)
async def logs_command(client: Client, message: Message):
    logger.info("/logs | owner=%s", message.from_user.id)
    try:
        with open("bot.log", "r") as fh:
            tail = fh.read()[-4000:]
        await message.reply_text(f"```\n{tail}\n```", reply_to_message_id=message.id)
    except FileNotFoundError:
        logger.error("bot.log not found")
        await message.reply_text("❌ ʟᴏɢ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ", reply_to_message_id=message.id)
    except Exception as exc:
        logger.error("logs_command error | err=%s", exc)
        await message.reply_text(f"❌ ᴇʀʀᴏʀ: {exc}", reply_to_message_id=message.id)


# ══════════════════════════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLERS
# ══════════════════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^start$"), group=2)
async def cb_start(client: Client, callback: CallbackQuery):
    logger.info("cb_start | user=%s", callback.from_user.id)
    text = (
        f"👋 *{small_caps('hello')} {callback.from_user.first_name}*,\n\n"
        f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
        f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ.\n\n"
        f"*{small_caps('features')}:*\n"
        f"⚡ ғᴀsᴛ ᴄʜᴜɴᴋ sᴛʀᴇᴀᴍɪɴɢ\n"
        f"🎬 ᴠɪᴅᴇᴏ sᴇᴇᴋɪɴɢ\n"
        f"📥 ʀᴇsᴜᴍᴀʙʟᴇ ᴅᴏᴡɴʟᴏᴀᴅs\n"
        f"🔐 sᴇᴄᴜʀᴇ ʟɪɴᴋs"
    )
    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^help$"), group=2)
async def cb_help(client: Client, callback: CallbackQuery):
    logger.info("cb_help | user=%s", callback.from_user.id)
    text = (
        f"📚 *{small_caps('help & guide')}*\n\n"
        f"*{small_caps('how to use')}:*\n"
        f"1️⃣ sᴇɴᴅ ᴀɴʏ ғɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        f"2️⃣ ɢᴇᴛ ɪɴsᴛᴀɴᴛ sᴛʀᴇᴀᴍ ʟɪɴᴋs\n"
        f"3️⃣ sʜᴀʀᴇ ʟɪɴᴋs ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"*{small_caps('supported files')}:*\n"
        f"🎬 ᴠɪᴅᴇᴏs\n"
        f"🎵 ᴀᴜᴅɪᴏ\n"
        f"📄 ᴅᴏᴄᴜᴍᴇɴᴛs\n"
        f"🖼️ ɪᴍᴀɢᴇs"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^about$"), group=2)
async def cb_about(client: Client, callback: CallbackQuery):
    from database import db

    logger.info("cb_about | user=%s", callback.from_user.id)
    try:
        stats = await db.get_stats()
    except Exception as exc:
        logger.error("cb_about stats error | err=%s", exc)
        stats = {"total_files": 0, "total_users": 0, "total_downloads": 0}

    text = (
        f"ℹ️ *{small_caps('about filestream bot')}*\n\n"
        f"🤖 *{small_caps('bot')}:* @{Config.BOT_USERNAME}\n"
        f"📊 *{small_caps('files')}:* {stats['total_files']}\n"
        f"👥 *{small_caps('users')}:* {stats['total_users']}\n"
        f"📥 *{small_caps('downloads')}:* {stats['total_downloads']}\n\n"
        f"💻 *{small_caps('developer')}:* @FLiX_LY\n"
        f"⚡ *{small_caps('version')}:* 2.0"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🏠 {small_caps('home')}", callback_data="start"),
        ]]),
    )
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^revoke_"), group=2)
async def cb_revoke(client: Client, callback: CallbackQuery):
    from database import db

    user_id = str(callback.from_user.id)
    token   = callback.data.replace("revoke_", "", 1)
    logger.info("cb_revoke | user=%s token=%s", user_id, token)

    file_data = await db.get_file_by_token(token)
    if not file_data:
        logger.warning("cb_revoke: file not found | user=%s token=%s", user_id, token)
        await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
        return

    if file_data["user_id"] != user_id and callback.from_user.id not in Config.OWNER_ID:
        logger.warning("cb_revoke: permission denied | user=%s token=%s", user_id, token)
        await callback.answer("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ", show_alert=True)
        return

    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as exc:
        logger.error("cb_revoke: dump delete error | msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])
    logger.info("cb_revoke: file removed | user=%s token=%s", user_id, token)
    await callback.message.edit_text(
        f"🗑️ *{small_caps('file revoked successfully')}!*\n\nᴀʟʟ ʟɪɴᴋs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
    )
    await callback.answer("✅ ғɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


@Client.on_callback_query(filters.regex(r"^view_"), group=2)
async def cb_view_file(client: Client, callback: CallbackQuery):
    from database import db

    user_id    = str(callback.from_user.id)
    message_id = callback.data.replace("view_", "", 1)
    logger.info("cb_view_file | user=%s msg_id=%s", user_id, message_id)

    file_data = await db.get_file(message_id)
    if not file_data:
        logger.warning("cb_view_file: not found | user=%s msg_id=%s", user_id, message_id)
        await callback.answer("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ", show_alert=True)
        return

    file_hash     = file_data["file_id"]
    base_url      = Config.URL or f"http://localhost:{Config.PORT}"
    stream_page   = f"{base_url}/stream/{file_hash}"
    download_link = f"{base_url}/dl/{file_hash}"
    telegram_link = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"

    safe_name      = escape_markdown(file_data["file_name"])
    formatted_size = format_size(file_data["file_size"])

    buttons = [
        [
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_page),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}",    switch_inline_query=file_hash),
        ],
        [InlineKeyboardButton(f"🗑️ {small_caps('revoke')}", callback_data=f"revoke_{file_data['secret_token']}")],
        [InlineKeyboardButton(f"⬅️ {small_caps('back')}",   callback_data="back_to_files")],
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


@Client.on_callback_query(filters.regex(r"^back_to_files$"), group=2)
async def cb_back_to_files(client: Client, callback: CallbackQuery):
    from database import db

    user_id = str(callback.from_user.id)
    logger.info("cb_back_to_files | user=%s", user_id)
    files   = await db.get_user_files(user_id, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 *{small_caps('your files')}*\n\nʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ғɪʟᴇs ʏᴇᴛ."
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
        f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ғɪʟᴇ:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await callback.answer()
