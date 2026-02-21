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
    return message.from_user.id in Config.OWNER_ID


owner = filters.create(_is_owner)


@Client.on_message(filters.command("setpublic") & filters.private & owner, group=2)
async def setpublic_command(client: Client, message: Message):
    from database import db

    current   = Config.get("public_bot", False)
    new_value = not current
    await Config.update(db.db, {"public_bot": new_value})

    mode = "ᴘᴜʙʟɪᴄ" if new_value else "ᴘʀɪᴠᴀᴛᴇ"
    await client.send_message(
        chat_id=message.chat.id,
        text=f"✅ ʙᴏᴛ ᴍᴏᴅᴇ ꜱᴇᴛ ᴛᴏ: *{mode}*",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("addsudo") & filters.private & owner, group=2)
async def addsudo_command(client: Client, message: Message):
    from database import db

    if len(message.command) < 2:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ᴜꜱᴀɢᴇ: `/addsudo <user_id>`",
            reply_to_message_id=message.id,
        )
        return

    try:
        target = message.command[1]
        await db.add_sudo_user(target, str(message.from_user.id))
        await client.send_message(
            chat_id=message.chat.id,
            text=f"✅ ᴜꜱᴇʀ `{target}` ᴀᴅᴅᴇᴅ ᴀꜱ ꜱᴜᴅᴏ ᴜꜱᴇʀ",
            reply_to_message_id=message.id,
        )
    except Exception as exc:
        logger.error("addsudo error: %s", exc)
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ ᴇʀʀᴏʀ: {exc}",
            reply_to_message_id=message.id,
        )


@Client.on_message(filters.command("rmsudo") & filters.private & owner, group=2)
async def rmsudo_command(client: Client, message: Message):
    from database import db

    if len(message.command) < 2:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ᴜꜱᴀɢᴇ: `/rmsudo <user_id>`",
            reply_to_message_id=message.id,
        )
        return

    try:
        target = message.command[1]
        result = await db.remove_sudo_user(target)
        if result:
            await client.send_message(
                chat_id=message.chat.id,
                text=f"✅ ᴜꜱᴇʀ `{target}` ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ",
                reply_to_message_id=message.id,
            )
        else:
            await client.send_message(
                chat_id=message.chat.id,
                text=f"❌ ᴜꜱᴇʀ `{target}` ɴᴏᴛ ꜰᴏᴜɴᴅ",
                reply_to_message_id=message.id,
            )
    except Exception as exc:
        logger.error("rmsudo error: %s", exc)
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ ᴇʀʀᴏʀ: {exc}",
            reply_to_message_id=message.id,
        )


@Client.on_message(filters.command("sudolist") & filters.private & owner, group=2)
async def sudolist_command(client: Client, message: Message):
    from database import db

    sudo_users = await db.get_sudo_users()
    if not sudo_users:
        await client.send_message(
            chat_id=message.chat.id,
            text=f"📋 *{small_caps('sudo users')}*\n\nɴᴏ ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ.",
            reply_to_message_id=message.id,
        )
        return

    text = f"📋 *{small_caps('sudo users')}* ({len(sudo_users)})\n\n"
    for u in sudo_users:
        text += f"• `{u['user_id']}`\n"
    await client.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("setbandwidth") & filters.private & owner, group=2)
async def setbandwidth_command(client: Client, message: Message):
    from database import db

    if len(message.command) < 2:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                "❌ ᴜꜱᴀɢᴇ: `/setbandwidth <bytes>`\n\n"
                "ᴇxᴀᴍᴘʟᴇꜱ:\n"
                "`/setbandwidth 107374182400` (100GB)\n"
                "`/setbandwidth 53687091200`  (50GB)"
            ),
            reply_to_message_id=message.id,
        )
        return

    try:
        new_limit = int(message.command[1])
        await Config.update(db.db, {"max_bandwidth": new_limit})
        await client.send_message(
            chat_id=message.chat.id,
            text=f"✅ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ꜱᴇᴛ ᴛᴏ: `{format_size(new_limit)}`",
            reply_to_message_id=message.id,
        )
    except ValueError as exc:
        logger.error("setbandwidth invalid value: %s", exc)
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ꜰᴏʀᴍᴀᴛ",
            reply_to_message_id=message.id,
        )


@Client.on_message(filters.command("setfsub") & filters.private & owner, group=2)
async def setfsub_command(client: Client, message: Message):
    from database import db

    current   = Config.get("fsub_mode", False)
    new_value = not current
    await Config.update(db.db, {"fsub_mode": new_value})

    status = "ᴇɴᴀʙʟᴇᴅ" if new_value else "ᴅɪꜱᴀʙʟᴇᴅ"
    await client.send_message(
        chat_id=message.chat.id,
        text=f"✅ ꜰᴏʀᴄᴇ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ: *{status}*",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("broadcast") & filters.private & owner, group=2)
async def broadcast_command(client: Client, message: Message):
    from database import db

    if not message.reply_to_message:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ *{small_caps('usage')}:*\n\n"
                f"ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴡɪᴛʜ `/broadcast` ᴛᴏ ꜱᴇɴᴅ ɪᴛ ᴛᴏ ᴀʟʟ ᴜꜱᴇʀꜱ"
            ),
            reply_to_message_id=message.id,
        )
        return

    users = await db.users.find({}).to_list(length=None)
    if not users:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ɴᴏ ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ",
            reply_to_message_id=message.id,
        )
        return

    status_msg = await client.send_message(
        chat_id=message.chat.id,
        text=f"📢 ꜱᴛᴀʀᴛɪɴɢ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴛᴏ {len(users)} ᴜꜱᴇʀꜱ...",
        reply_to_message_id=message.id,
    )
    success = failed = 0

    for user in users:
        try:
            await message.reply_to_message.copy(chat_id=int(user["user_id"]))
            success += 1
        except Exception as exc:
            logger.error("broadcast failed: target=%s err=%s", user["user_id"], exc)
            failed += 1

    await status_msg.edit_text(
        f"✅ *{small_caps('broadcast completed')}*\n\n"
        f"📤 *{small_caps('sent')}:* {success}\n"
        f"❌ *{small_caps('failed')}:* {failed}"
    )


@Client.on_message(filters.command("revokeall") & filters.private & owner, group=2)
async def revokeall_command(client: Client, message: Message):
    from database import db

    stats       = await db.get_stats()
    total_files = stats["total_files"]

    if total_files == 0:
        await client.send_message(
            chat_id=message.chat.id,
            text="📂 ɴᴏ ꜰɪʟᴇꜱ ᴛᴏ ᴅᴇʟᴇᴛᴇ.",
            reply_to_message_id=message.id,
        )
        return

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"⚠️ *{small_caps('warning')}*\n\n"
            f"ᴛʜɪꜱ ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ *{total_files}* ꜰɪʟᴇꜱ.\n"
            f"ꜱᴇɴᴅ `/confirmdelete` ᴛᴏ ᴄᴏɴꜰɪʀᴍ."
        ),
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("confirmdelete") & filters.private & owner, group=2)
async def confirmdelete_command(client: Client, message: Message):
    from database import db

    msg = await client.send_message(
        chat_id=message.chat.id,
        text="🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ꜰɪʟᴇꜱ...",
        reply_to_message_id=message.id,
    )
    deleted_count = await db.delete_all_files()
    await msg.edit_text(
        f"🗑️ *{small_caps('all files deleted')}!*\n\n"
        f"ᴅᴇʟᴇᴛᴇᴅ {deleted_count} ꜰɪʟᴇꜱ."
    )


@Client.on_message(filters.command("logs") & filters.private & owner, group=2)
async def logs_command(client: Client, message: Message):
    try:
        with open("bot.log", "r") as fh:
            tail = fh.read()[-4000:]
        await client.send_message(
            chat_id=message.chat.id,
            text=f"```\n{tail}\n```",
            reply_to_message_id=message.id,
        )
    except FileNotFoundError:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ ʟᴏɢ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ",
            reply_to_message_id=message.id,
        )
    except Exception as exc:
        logger.error("logs_command error: %s", exc)
        await client.send_message(
            chat_id=message.chat.id,
            text=f"❌ ᴇʀʀᴏʀ: {exc}",
            reply_to_message_id=message.id,
        )


@Client.on_callback_query(filters.regex(r"^start$"), group=2)
async def cb_start(client: Client, callback: CallbackQuery):
    text = (
        f"👋 *{small_caps('hello')} {callback.from_user.first_name}*,\n\n"
        f"ɪ ᴀᴍ ᴀ *{small_caps('premium file stream bot')}*.\n\n"
        f"📂 *{small_caps('send me any file')}* (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ) "
        f"ᴀɴᴅ ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ꜱᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋ ꜰᴏʀ ʏᴏᴜ."
    )
    buttons = [[
        InlineKeyboardButton(f"📚 {small_caps('help')}",  callback_data="help"),
        InlineKeyboardButton(f"ℹ️ {small_caps('about')}", callback_data="about"),
    ]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^help$"), group=2)
async def cb_help(client: Client, callback: CallbackQuery):
    text = (
        f"📚 *{small_caps('help & guide')}*\n\n"
        f"*{small_caps('how to use')}:*\n"
        f"1️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ\n"
        f"2️⃣ ɢᴇᴛ ɪɴꜱᴛᴀɴᴛ ꜱᴛʀᴇᴀᴍ & ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ\n"
        f"3️⃣ ꜱʜᴀʀᴇ ʟɪɴᴋꜱ ᴀɴʏᴡʜᴇʀᴇ!\n\n"
        f"*{small_caps('supported files')}:*\n"
        f"🎬 ᴠɪᴅᴇᴏꜱ\n"
        f"🎵 ᴀᴜᴅɪᴏ\n"
        f"📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ\n"
        f"🖼️ ɪᴍᴀɢᴇꜱ"
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

    try:
        stats = await db.get_stats()
    except Exception as exc:
        logger.error("cb_about stats error: %s", exc)
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

    user_id   = str(callback.from_user.id)
    file_hash = callback.data.replace("revoke_", "", 1)

    file_data = await db.get_file_by_hash(file_hash)
    if not file_data:
        await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ", show_alert=True)
        return

    if file_data["user_id"] != user_id and callback.from_user.id not in Config.OWNER_ID:
        await callback.answer("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪꜱꜱɪᴏɴ", show_alert=True)
        return

    try:
        await client.delete_messages(Config.DUMP_CHAT_ID, int(file_data["message_id"]))
    except Exception as exc:
        logger.error("cb_revoke dump delete error: msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])

    await callback.message.edit_text(
        f"🗑️ *{small_caps('file revoked successfully')}!*\n\n"
        f"ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


@Client.on_callback_query(filters.regex(r"^view_"), group=2)
async def cb_view_file(client: Client, callback: CallbackQuery):
    from database import db

    user_id    = str(callback.from_user.id)
    message_id = callback.data.replace("view_", "", 1)

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
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
            InlineKeyboardButton(f"📥 {small_caps('download')}", url=download_link),
        ],
        [
            InlineKeyboardButton(f"💬 {small_caps('telegram')}", url=telegram_link),
            InlineKeyboardButton(f"🔁 {small_caps('share')}", switch_inline_query=file_hash),
        ],
        [InlineKeyboardButton(
            f"🗑️ {small_caps('revoke')}",
            callback_data=f"revoke_{file_hash}",
        )],
        [InlineKeyboardButton(
            f"⬅️ {small_caps('back')}",
            callback_data="back_to_files",
        )],
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
    files   = await db.get_user_files(user_id, limit=50)

    if not files:
        await callback.message.edit_text(
            f"📂 *{small_caps('your files')}*\n\nʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ꜰɪʟᴇꜱ ʏᴇᴛ."
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
        f"📂 *{small_caps('your files')}* ({len(files)} ᴛᴏᴛᴀʟ)\n\nᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ꜰɪʟᴇ:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    await callback.answer()
