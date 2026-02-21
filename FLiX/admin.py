import logging

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import Config
from helper import small_caps, format_size

logger = logging.getLogger(__name__)


# ── Owner filter ──────────────────────────────────────────────────────────────

def _is_owner(_, __, message: Message) -> bool:
    return message.from_user.id in Config.OWNER_ID


owner = filters.create(_is_owner)


# ──────────────────────────────────────────────────────────────────────────────
# /setpublic
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /addsudo
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /rmsudo
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /sudolist
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /setbandwidth
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /setfsub
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /broadcast
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /revokeall + /confirmdelete
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# /logs
# ──────────────────────────────────────────────────────────────────────────────

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
