import asyncio
import logging

from pyrogram import Client, filters, StopPropagation
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from helper import small_caps, format_size, escape_markdown

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════ #
#  Owner filter                                                               #
# ═══════════════════════════════════════════════════════════════════════════ #

def _is_owner(_, __, message: Message) -> bool:
    return message.from_user.id in Config.OWNER_ID


owner = filters.create(_is_owner)


async def check_owner(client: Client, event) -> bool:
    user_id = event.from_user.id

    if user_id not in Config.OWNER_ID:
        if isinstance(event, Message):
            await client.send_message(
                chat_id=event.chat.id,
                text="🚫 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱!\n\n🔒 This command is **restricted** to bot admins.",
                reply_to_message_id=event.id,
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "🚫 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱!\n\n🔒 This action is restricted to bot admins.",
                show_alert=True,
            )
        return False
    return True


async def is_member(client, message, target_id: int = None) -> bool:
    check_id = target_id or Config.get("fsub_chat_id", 0)
    if check_id == 0:
        return True

    enforce_fsub = target_id is None and Config.get("fsub_mode", False)
    if target_id is None and not enforce_fsub:
        return True

    try:
        member = await client.get_chat_member(check_id, message.from_user.id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )

    except UserNotParticipant:
        if target_id is None:
            await client.send_photo(
                chat_id=message.chat.id,
                photo="https://t.me/FLiX_Logos/331",
                caption=(
                    f"ʜᴇʏ **{message.from_user.mention}**,\n\n"
                    "🧩 ᴛᴏ ᴜɴʟᴏᴄᴋ ᴍʏ ғᴜʟʟ ғᴇᴀᴛᴜʀᴇ ꜱᴇᴛ,\n"
                    "ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇꜱ ᴄʜᴀɴɴᴇʟ ꜰɪʀꜱᴛ!\n\n"
                    "🚀 ᴊᴏɪɴ ɴᴏᴡ, ᴛʜᴇɴ ʜɪᴛ **/start** ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ʏᴏᴜʀ ᴍɪꜱꜱɪᴏɴ."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✨ ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇꜱ ✨", url=Config.get("fsub_inv_link"))]]
                ),
            )
        return False

    except ChatAdminRequired:
        logger.warning(f"Bot lacks permission to check is_member in chat {check_id}.")
        return True

    except Exception as e:
        logger.error(f"Membership check failed for user {message.from_user.id} in chat {check_id}: {e}")
        return True


# ═══════════════════════════════════════════════════════════════════════════ #
#  Panel renderer                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

async def show_panel(client: Client, source, panel_type: str):
    from database import db

    config = Config.all()
    msg = source.message if isinstance(source, CallbackQuery) else source

    # ── Main panel ──────────────────────────────────────────────────────
    if panel_type == "main_panel":
        max_bw    = Config.get("max_bandwidth", 107374182400)
        bw_toggle = Config.get("bandwidth_mode", True)
        text = (
            "✨ **Bᴏᴛ Sᴇᴛᴛɪɴɢꜱ Pᴀɴᴇʟ** ✨\n\n"
            f"📡 **Bᴀɴᴅᴡɪᴅᴛʜ**  : {'🟢 ᴀᴄᴛɪᴠᴇ' if bw_toggle else '🔴 ɪɴᴀᴄᴛɪᴠᴇ'} | `{format_size(max_bw)}`\n"
            f"👥 **Sᴜᴅᴏ Uꜱᴇʀꜱ** : ᴍᴀɴᴀɢᴇ ᴀᴄᴄᴇꜱꜱ\n"
            f"🤖 **Bᴏᴛ Mᴏᴅᴇ**  : {'🟢 ᴘᴜʙʟɪᴄ' if config.get('public_bot') else '🔴 ᴘʀɪᴠᴀᴛᴇ'}\n"
            f"📢 **Fᴏʀᴄᴇ Sᴜʙ** : {'🟢 ᴀᴄᴛɪᴠᴇ' if config.get('fsub_mode') else '🔴 ɪɴᴀᴄᴛɪᴠᴇ'}\n\n"
            "👇 ᴄʜᴏᴏꜱᴇ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ᴛᴏ ᴄᴏɴꜰɪɢᴜʀᴇ."
        )
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📡 ʙᴀɴᴅᴡɪᴅᴛʜ",    callback_data="settings_bandwidth"),
                InlineKeyboardButton("👥 ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ",   callback_data="settings_sudo"),
            ],
            [
                InlineKeyboardButton("🤖 ʙᴏᴛ ᴍᴏᴅᴇ",     callback_data="settings_botmode"),
                InlineKeyboardButton("📢 ꜰᴏʀᴄᴇ ꜱᴜʙ",    callback_data="settings_fsub"),
            ],
            [
                InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="settings_close"),
            ],
        ])

    # ── Bandwidth panel ──────────────────────────────────────────────────
    elif panel_type == "bandwidth_panel":
        max_bw    = Config.get("max_bandwidth", 107374182400)
        bw_toggle = Config.get("bandwidth_mode", True)
        text = (
            "💠 **Bᴀɴᴅᴡɪᴅᴛʜ Sᴇᴛᴛɪɴɢꜱ** 💠\n\n"
            f"⚡ **Mᴏᴅᴇ**   : {'🟢 ᴀᴄᴛɪᴠᴇ' if bw_toggle else '🔴 ɪɴᴀᴄᴛɪᴠᴇ'}\n"
            f"📊 **Lɪᴍɪᴛ** : `{format_size(max_bw)}`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ ᴛᴏɢɢʟᴇ", callback_data="toggle_bandwidth")],
            [InlineKeyboardButton("✏️ ꜱᴇᴛ ʟɪᴍɪᴛ", callback_data="set_bandwidth_limit")],
            [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="settings_back")],
        ])

    # ── Sudo users panel ─────────────────────────────────────────────────
    elif panel_type == "sudo_panel":
        sudo_users = await db.get_sudo_users()
        count = len(sudo_users)
        lines = "\n".join(f"  • `{u['user_id']}`" for u in sudo_users) if sudo_users else "  ɴᴏɴᴇ"
        text = (
            "💠 **Sᴜᴅᴏ Uꜱᴇʀꜱ** 💠\n\n"
            f"👥 **Cᴏᴜɴᴛ** : `{count}`\n\n"
            f"**Lɪꜱᴛ:**\n{lines}"
        )
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ ᴀᴅᴅ",    callback_data="sudo_add"),
                InlineKeyboardButton("➖ ʀᴇᴍᴏᴠᴇ", callback_data="sudo_remove"),
            ],
            [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="settings_back")],
        ])

    # ── Bot mode panel ───────────────────────────────────────────────────
    elif panel_type == "botmode_panel":
        public = config.get("public_bot", False)
        text = (
            "💠 **Bᴏᴛ Mᴏᴅᴇ Sᴇᴛᴛɪɴɢꜱ** 💠\n\n"
            f"⚡ **Cᴜʀʀᴇɴᴛ Mᴏᴅᴇ** : {'🌍 ᴘᴜʙʟɪᴄ' if public else '🔒 ᴘʀɪᴠᴀᴛᴇ'}\n\n"
            "🌍 **Pᴜʙʟɪᴄ** — ᴀɴʏᴏɴᴇ ᴄᴀɴ ᴜꜱᴇ ᴛʜᴇ ʙᴏᴛ\n"
            "🔒 **Pʀɪᴠᴀᴛᴇ** — ᴏɴʟʏ ꜱᴜᴅᴏ/ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔓 ꜱᴇᴛ ᴘᴜʙʟɪᴄ" if not public else "🔒 ꜱᴇᴛ ᴘʀɪᴠᴀᴛᴇ",
                callback_data="toggle_botmode",
            )],
            [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="settings_back")],
        ])

    # ── Force-sub panel ──────────────────────────────────────────────────
    elif panel_type == "fsub_panel":
        fsub_id   = config.get("fsub_chat_id", 0)
        fsub_name = "Nᴏᴛ Sᴇᴛ"
        if fsub_id:
            try:
                fsub_name = (await client.get_chat(fsub_id)).title
            except Exception:
                fsub_name = "❓ Uɴᴋɴᴏᴡɴ"

        text = (
            "💠 **Fᴏʀᴄᴇ Sᴜʙ Sᴇᴛᴛɪɴɢꜱ** 💠\n\n"
            f"⚡ **Mᴏᴅᴇ**          : {'🟢 ᴀᴄᴛɪᴠᴇ' if config.get('fsub_mode') else '🔴 ɪɴᴀᴄᴛɪᴠᴇ'}\n"
            f"🆔 **Cʜᴀɴɴᴇʟ Iᴅ**   : `{fsub_id or 'Nᴏᴛ Sᴇᴛ'}`\n"
            f"📛 **Cʜᴀɴɴᴇʟ Nᴀᴍᴇ** : `{fsub_name}`\n"
            f"🔗 **Iɴᴠɪᴛᴇ Lɪɴᴋ**  : `{config.get('fsub_inv_link') or 'Nᴏᴛ Sᴇᴛ'}`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ ᴛᴏɢɢʟᴇ", callback_data="toggle_fsub")],
            [
                InlineKeyboardButton("🆔 Cʜᴀɴɴᴇʟ Iᴅ", callback_data="set_fsub_id"),
                InlineKeyboardButton("🔗 Iɴᴠɪᴛᴇ",      callback_data="set_fsub_link"),
            ],
            [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="settings_back")],
        ])

    else:
        return

    # ── Send or edit ─────────────────────────────────────────────────────
    if isinstance(source, CallbackQuery):
        try:
            await source.message.edit_text(
                text,
                reply_markup=buttons,
                disable_web_page_preview=True,
            )
        except Exception:
            await client.send_message(
                chat_id=source.message.chat.id,
                text=text,
                reply_markup=buttons,
                disable_web_page_preview=True,
            )
    else:
        await client.send_message(
            chat_id=source.chat.id,
            text=text,
            reply_to_message_id=source.id,
            reply_markup=buttons,
            disable_web_page_preview=True,
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  Ask-input helper                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

_pending: dict[int, asyncio.Future] = {}


@Client.on_message(filters.text & filters.private, group=99)
async def _catch_pending(client: Client, message: Message):
    uid = message.from_user.id
    if uid in _pending and not _pending[uid].done():
        _pending[uid].set_result(message)
        raise StopPropagation


async def ask_input(
    client: Client, user_id: int, prompt: str, timeout: int = 60
) -> str | None:
    loop   = asyncio.get_event_loop()
    future = loop.create_future()
    _pending[user_id] = future

    ask_msg = None
    reply   = None
    try:
        ask_msg = await client.send_message(user_id, prompt)
        reply   = await asyncio.wait_for(future, timeout=timeout)
        return reply.text.strip() if reply and reply.text else None
    except asyncio.TimeoutError:
        logger.debug("ask_input timed out for user %s", user_id)
        return None
    except Exception as exc:
        logger.debug("ask_input error for user %s: %s", user_id, exc)
        return None
    finally:
        _pending.pop(user_id, None)
        for m in (ask_msg, reply):
            if m:
                try:
                    await m.delete()
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════════ #
#  /bot_settings command                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

@Client.on_message(filters.command("bot_settings") & filters.private, group=2)
async def open_settings(client: Client, message: Message):
    if not await check_owner(client, message):
        return
    await show_panel(client, message, "main_panel")


# ═══════════════════════════════════════════════════════════════════════════ #
#  Callback handler                                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

@Client.on_callback_query(
    filters.regex(r"^(settings_|toggle_|set_|sudo_).+"),
    group=2,
)
async def settings_callback(client: Client, callback: CallbackQuery):
    from database import db

    data   = callback.data
    config = Config.all()

    if not await check_owner(client, callback):
        return

    # ── Panel navigation ────────────────────────────────────────────────
    panel_nav = {
        "settings_bandwidth": ("bandwidth_panel", "📡 ʙᴀɴᴅᴡɪᴅᴛʜ ꜱᴇᴛᴛɪɴɢꜱ"),
        "settings_sudo":      ("sudo_panel",      "👥 ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ"),
        "settings_botmode":   ("botmode_panel",   "🤖 ʙᴏᴛ ᴍᴏᴅᴇ ꜱᴇᴛᴛɪɴɢꜱ"),
        "settings_fsub":      ("fsub_panel",      "📌 ꜰᴏʀᴄᴇ ꜱᴜʙ ꜱᴇᴛᴛɪɴɢꜱ"),
        "settings_back":      ("main_panel",      "⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"),
    }
    if data in panel_nav:
        panel, toast = panel_nav[data]
        await callback.answer(toast, show_alert=False)
        return await show_panel(client, callback, panel)

    if data == "settings_close":
        try:
            await callback.answer("❌ ᴄʟᴏꜱɪɴɢ", show_alert=True)
            await callback.message.delete()
        except Exception:
            pass
        return

    # ── Toggles ─────────────────────────────────────────────────────────
    if data == "toggle_bandwidth":
        new_val = not config.get("bandwidth_mode", True)
        await Config.update(db.db, {"bandwidth_mode": new_val})
        await callback.answer("✅ Bᴀɴᴅᴡɪᴅᴛʜ ᴍᴏᴅᴇ ᴛᴏɢɢʟᴇᴅ!", show_alert=True)
        return await show_panel(client, callback, "bandwidth_panel")

    if data == "toggle_botmode":
        new_val = not config.get("public_bot", False)
        await Config.update(db.db, {"public_bot": new_val})
        mode = "ᴘᴜʙʟɪᴄ" if new_val else "ᴘʀɪᴠᴀᴛᴇ"
        await callback.answer(f"✅ Bᴏᴛ ꜱᴇᴛ ᴛᴏ {mode}!", show_alert=True)
        return await show_panel(client, callback, "botmode_panel")

    if data == "toggle_fsub":
        new_val = not config.get("fsub_mode", False)
        await Config.update(db.db, {"fsub_mode": new_val})
        await callback.answer("✅ Fᴏʀᴄᴇ ꜱᴜʙ ᴛᴏɢɢʟᴇᴅ!", show_alert=True)
        return await show_panel(client, callback, "fsub_panel")

    # ── Bandwidth limit ──────────────────────────────────────────────────
    if data == "set_bandwidth_limit":
        text = await ask_input(
            client, callback.from_user.id,
            "📡 **Sᴇɴᴅ ʙᴀɴᴅᴡɪᴅᴛʜ ʟɪᴍɪᴛ ɪɴ ʙʏᴛᴇꜱ**\n\n"
            "ᴇxᴀᴍᴘʟᴇꜱ:\n"
            "`107374182400` — 100 GB\n"
            "`53687091200`  — 50 GB\n"
            "`10737418240`  — 10 GB\n\n"
            "Sᴇɴᴅ `0` ᴛᴏ ʀᴇꜱᴇᴛ ᴛᴏ 100 GB.",
        )
        if text is None:
            return
        if not text.isdigit():
            await callback.answer("❌ Iɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ!", show_alert=True)
            return
        new_limit = int(text) or 107374182400
        await Config.update(db.db, {"max_bandwidth": new_limit})
        await callback.answer(
            f"✅ Lɪᴍɪᴛ ꜱᴇᴛ ᴛᴏ {format_size(new_limit)}!",
            show_alert=True,
        )
        return await show_panel(client, callback, "bandwidth_panel")

    # ── Sudo add ─────────────────────────────────────────────────────────
    if data == "sudo_add":
        text = await ask_input(
            client, callback.from_user.id,
            "👥 **Sᴇɴᴅ ᴜꜱᴇʀ ID ᴛᴏ ᴀᴅᴅ ᴀꜱ ꜱᴜᴅᴏ**",
        )
        if text is None:
            return
        if not text.lstrip("-").isdigit():
            await callback.answer("❌ Iɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ID!", show_alert=True)
            return
        await db.add_sudo_user(text, str(callback.from_user.id))
        await callback.answer(f"✅ `{text}` ᴀᴅᴅᴇᴅ ᴀꜱ ꜱᴜᴅᴏ!", show_alert=True)
        return await show_panel(client, callback, "sudo_panel")

    # ── Sudo remove ──────────────────────────────────────────────────────
    if data == "sudo_remove":
        text = await ask_input(
            client, callback.from_user.id,
            "👥 **Sᴇɴᴅ ᴜꜱᴇʀ ID ᴛᴏ ʀᴇᴍᴏᴠᴇ ꜰʀᴏᴍ ꜱᴜᴅᴏ**",
        )
        if text is None:
            return
        result = await db.remove_sudo_user(text)
        if result:
            await callback.answer(f"✅ `{text}` ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ꜱᴜᴅᴏ!", show_alert=True)
        else:
            await callback.answer(f"❌ `{text}` ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ꜱᴜᴅᴏ ʟɪꜱᴛ.", show_alert=True)
        return await show_panel(client, callback, "sudo_panel")

    # ── Force-sub settings ───────────────────────────────────────────────
    if data == "set_fsub_id":
        text = await ask_input(
            client, callback.from_user.id,
            "📢 **Sᴇɴᴅ ᴛʜᴇ Cʜᴀɴɴᴇʟ ID**\n\n"
            "📌 Fᴏʀᴍᴀᴛ: `-100xxxxxxxxxx`\n"
            "➡️ Sᴇɴᴅ `0` ᴛᴏ ᴜɴꜱᴇᴛ.",
        )
        if text is None:
            return

        value = int(text) if text != "0" and text.lstrip("-").isdigit() else 0

        if value == 0:
            await Config.update(db.db, {"fsub_chat_id": 0, "fsub_inv_link": ""})
            await callback.answer("✅ Fꜱᴜʙ Cʜᴀɴɴᴇʟ ᴜɴꜱᴇᴛ!", show_alert=True)
            return await show_panel(client, callback, "fsub_panel")

        if not str(value).startswith("-100"):
            return await callback.answer(
                "❌ Iɴᴠᴀʟɪᴅ ID!\n\n📌 Cʜᴀɴɴᴇʟ ID ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ `-100`",
                show_alert=True,
            )

        try:
            me     = await client.get_me()
            member = await client.get_chat_member(value, me.id)

            if member.status not in (
                ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
            ):
                return await callback.answer(
                    "❌ Nᴏ Aᴅᴍɪɴ Rɪɢʜᴛꜱ!\n\n⚡ I ᴍᴜꜱᴛ ʙᴇ Aᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ Cʜᴀɴɴᴇʟ.",
                    show_alert=True,
                )

            rights = getattr(member, "privileges", None)
            if rights and not rights.can_invite_users:
                return await callback.answer(
                    "❌ Mɪꜱꜱɪɴɢ Pᴇʀᴍɪꜱꜱɪᴏɴ!\n\n"
                    "👤 Pʟᴇᴀꜱᴇ ɢʀᴀɴᴛ: 🔑 `Aᴅᴅ Sᴜʙꜱᴄʀɪʙᴇʀꜱ` ʀɪɢʜᴛ",
                    show_alert=True,
                )

            try:
                inv = await client.export_chat_invite_link(value)
            except Exception:
                inv = ""

            await Config.update(db.db, {"fsub_chat_id": value, "fsub_inv_link": inv})
            await callback.answer(
                "✅ Fꜱᴜʙ Cʜᴀɴɴᴇʟ Sᴀᴠᴇᴅ!\n\n🆔 ID + 🔗 Iɴᴠɪᴛᴇ Lɪɴᴋ ᴀᴅᴅᴇᴅ.",
                show_alert=True,
            )

        except Exception as exc:
            return await callback.answer(f"❌ Eʀʀᴏʀ:\n`{exc}`", show_alert=True)

        return await show_panel(client, callback, "fsub_panel")

    if data == "set_fsub_link":
        text = await ask_input(
            client, callback.from_user.id,
            "🔗 **Sᴇɴᴅ Iɴᴠɪᴛᴇ Lɪɴᴋ**\n\nSend `0` to unset.",
        )
        if text is not None:
            await Config.update(db.db, {"fsub_inv_link": "" if text == "0" else text})
            await callback.answer("✅ Fꜱᴜʙ ɪɴᴠɪᴛᴇ ʟɪɴᴋ ᴜᴘᴅᴀᴛᴇᴅ!", show_alert=True)
            return await show_panel(client, callback, "fsub_panel")
        return


# ═══════════════════════════════════════════════════════════════════════════ #
#  Legacy admin commands                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

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


# ── Inline callbacks (Start / Help / About / Revoke / View / Files) ─────── #

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
        f"🎬 ᴠɪᴅᴇᴏꜱ\n🎵 ᴀᴜᴅɪᴏ\n📄 ᴅᴏᴄᴜᴍᴇɴᴛꜱ\n🖼️ ɪᴍᴀɢᴇꜱ"
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
        f"⚡ *{small_caps('version')}:* 2.1"
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
        logger.error("cb_revoke dump delete: msg=%s err=%s", file_data["message_id"], exc)

    await db.delete_file(file_data["message_id"])
    await callback.message.edit_text(
        f"🗑️ *{small_caps('file revoked successfully')}!*\n\nᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
    )
    await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


@Client.on_callback_query(filters.regex(r"^view_"), group=2)
async def cb_view_file(client: Client, callback: CallbackQuery):
    from database import db

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
            InlineKeyboardButton(f"🎬 {small_caps('stream')}",   url=stream_link),
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
        f"✅ *{small_caps('file details')}*\n\n"
        f"📂 *{small_caps('name')}:* `{safe_name}`\n"
        f"💾 *{small_caps('size')}:* `{formatted_size}`\n"
        f"📊 *{small_caps('type')}:* `{file_data['file_type']}`\n"
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
