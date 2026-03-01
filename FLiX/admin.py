import asyncio
import logging
import os
import time

from pyrogram import Client, filters, StopPropagation
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database import db
from helper import small_caps, format_size, escape_markdown, format_uptime, human_size, check_owner

logger = logging.getLogger(__name__)


async def show_panel(client: Client, source, panel_type: str):
    config = Config.all()
    msg    = source.message if isinstance(source, CallbackQuery) else source

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
                InlineKeyboardButton("📡 ʙᴀɴᴅᴡɪᴅᴛʜ",  callback_data="settings_bandwidth"),
                InlineKeyboardButton("👥 ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ", callback_data="settings_sudo"),
            ],
            [
                InlineKeyboardButton("🤖 ʙᴏᴛ ᴍᴏᴅᴇ",   callback_data="settings_botmode"),
                InlineKeyboardButton("📢 ꜰᴏʀᴄᴇ ꜱᴜʙ",  callback_data="settings_fsub"),
            ],
            [InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="settings_close")],
        ])

    elif panel_type == "bandwidth_panel":
        max_bw    = Config.get("max_bandwidth", 107374182400)
        bw_toggle = Config.get("bandwidth_mode", True)
        bw_stats  = await db.get_bandwidth_stats()
        bw_used   = bw_stats["total_bandwidth"]
        bw_today  = bw_stats["today_bandwidth"]
        bw_pct    = (bw_used / max_bw * 100) if max_bw else 0
        text = (
            "💠 **Bᴀɴᴅᴡɪᴅᴛʜ Sᴇᴛᴛɪɴɢꜱ** 💠\n\n"
            f"⚡ **Mᴏᴅᴇ**       : {'🟢 ᴀᴄᴛɪᴠᴇ' if bw_toggle else '🔴 ɪɴᴀᴄᴛɪᴠᴇ'}\n"
            f"📊 **Lɪᴍɪᴛ**      : `{format_size(max_bw)}`\n"
            f"📤 **Uꜱᴇᴅ (ᴛᴏᴛᴀʟ)**: `{format_size(bw_used)}` ({bw_pct:.1f}%)\n"
            f"📅 **Uꜱᴇᴅ ᴛᴏᴅᴀʏ** : `{format_size(bw_today)}`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ ᴛᴏɢɢʟᴇ",         callback_data="toggle_bandwidth")],
            [InlineKeyboardButton("✏️ ꜱᴇᴛ ʟɪᴍɪᴛ",     callback_data="set_bandwidth_limit")],
            [InlineKeyboardButton("🔄 ʀᴇꜱᴇᴛ ᴜꜱᴀɢᴇ",   callback_data="reset_bandwidth")],
            [InlineKeyboardButton("⬅️ ʙᴀᴄᴋ",           callback_data="settings_back")],
        ])

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

    if isinstance(source, CallbackQuery):
        try:
            await source.message.edit_text(text, reply_markup=buttons)
        except Exception:
            await client.send_message(
                chat_id=source.message.chat.id,
                text=text,
                reply_markup=buttons,
            )
    else:
        await client.send_message(
            chat_id=source.chat.id,
            text=text,
            reply_to_message_id=source.id,
            reply_markup=buttons,
        )


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


@Client.on_message(filters.command("bot_settings") & filters.private, group=2)
async def open_settings(client: Client, message: Message):
    if not await check_owner(client, message):
        return
    await show_panel(client, message, "main_panel")


@Client.on_callback_query(
    filters.regex(r"^(settings_|toggle_|set_|sudo_|reset_).+"),
    group=2,
)
async def settings_callback(client: Client, callback: CallbackQuery):
    data   = callback.data
    config = Config.all()

    if not await check_owner(client, callback):
        return

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
        await callback.answer(f"✅ Lɪᴍɪᴛ ꜱᴇᴛ ᴛᴏ {format_size(new_limit)}!", show_alert=True)
        return await show_panel(client, callback, "bandwidth_panel")

    if data == "reset_bandwidth":
        await callback.answer("🔄 Rᴇꜱᴇᴛᴛɪɴɢ ʙᴀɴᴅᴡɪᴅᴛʜ ᴜꜱᴀɢᴇ…", show_alert=False)
        ok = await db.reset_bandwidth()
        if ok:
            await callback.answer("✅ Bᴀɴᴅᴡɪᴅᴛʜ ᴜꜱᴀɢᴇ ʀᴇꜱᴇᴛ ᴛᴏ ᴢᴇʀᴏ!", show_alert=True)
        else:
            await callback.answer("❌ Fᴀɪʟᴇᴅ ᴛᴏ ʀᴇꜱᴇᴛ ʙᴀɴᴅᴡɪᴅᴛʜ.", show_alert=True)
        return await show_panel(client, callback, "bandwidth_panel")

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
            await callback.answer("✅ Fꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴜɴꜱᴇᴛ!", show_alert=True)
            return await show_panel(client, callback, "fsub_panel")

        if not str(value).startswith("-100"):
            return await callback.answer(
                "❌ Iɴᴠᴀʟɪᴅ ID!\n\n📌 Cʜᴀɴɴᴇʟ ID ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ `-100`",
                show_alert=True,
            )

        try:
            me     = await client.get_me()
            member = await client.get_chat_member(value, me.id)

            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                return await callback.answer(
                    "❌ Nᴏ Aᴅᴍɪɴ Rɪɢʜᴛꜱ!\n\n⚡ I ᴍᴜꜱᴛ ʙᴇ Aᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ.",
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
                "✅ Fꜱᴜʙ ᴄʜᴀɴɴᴇʟ ꜱᴀᴠᴇᴅ!\n\n🆔 ID + 🔗 Iɴᴠɪᴛᴇ ʟɪɴᴋ ᴀᴅᴅᴇᴅ.",
                show_alert=True,
            )

        except Exception as exc:
            return await callback.answer(f"❌ Eʀʀᴏʀ:\n`{exc}`", show_alert=True)

        return await show_panel(client, callback, "fsub_panel")

    if data == "set_fsub_link":
        text = await ask_input(
            client, callback.from_user.id,
            "🔗 **Sᴇɴᴅ ɪɴᴠɪᴛᴇ ʟɪɴᴋ**\n\nSend `0` to unset.",
        )
        if text is not None:
            await Config.update(db.db, {"fsub_inv_link": "" if text == "0" else text})
            await callback.answer("✅ Fꜱᴜʙ ɪɴᴠɪᴛᴇ ʟɪɴᴋ ᴜᴘᴅᴀᴛᴇᴅ!", show_alert=True)
            return await show_panel(client, callback, "fsub_panel")
        return


@Client.on_message(filters.command("adminstats") & filters.private, group=2)
async def adminstats_command(client: Client, message: Message):
    if not await check_owner(client, message):
        return

    uptime_str = format_uptime(time.time() - Config.UPTIME)
    stats      = await db.get_stats()
    bw_stats   = await db.get_bandwidth_stats()

    max_bw  = Config.get("max_bandwidth", 107374182400)
    bw_used = bw_stats["total_bandwidth"]
    bw_pct  = (bw_used / max_bw * 100) if max_bw else 0
    bw_mode = "🟢 ᴀᴄᴛɪᴠᴇ" if Config.get("bandwidth_mode", True) else "🔴 ɪɴᴀᴄᴛɪᴠᴇ"

    text = (
        f"📊 **{small_caps('admin statistics')}**\n\n"
        f"⏱️ **{small_caps('uptime')}:**         `{uptime_str}`\n\n"
        f"👥 **{small_caps('total users')}:**     `{stats['total_users']}`\n"
        f"📂 **{small_caps('total files')}:**     `{stats['total_files']}`\n\n"
        f"📡 **{small_caps('bandwidth mode')}:**  {bw_mode}\n"
        f"📶 **{small_caps('bw limit')}:**        `{format_size(max_bw)}`\n"
        f"📤 **{small_caps('bw used total')}:**   `{format_size(bw_used)}` ({bw_pct:.1f}%)\n"
        f"📅 **{small_caps('bw used today')}:**   `{format_size(bw_stats['today_bandwidth'])}`"
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("revoke") & filters.private, group=0)
async def revoke_command(client: Client, message: Message):
    if not await check_owner(client, message):
        return

    if len(message.command) < 2:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ **{small_caps('invalid command')}**\n\n"
                "ᴜꜱᴀɢᴇ: `/revoke <file_hash>`"
            ),
            reply_to_message_id=message.id,
        )
        return

    file_hash = message.command[1]
    file_data = await db.get_file_by_hash(file_hash)

    if not file_data:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"❌ **{small_caps('file not found')}**\n\n"
                "ᴛʜᴇ ꜰɪʟᴇ ᴅᴏᴇꜱɴ'ᴛ ᴇxɪꜱᴛ ᴏʀ ʜᴀꜱ ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
            ),
            reply_to_message_id=message.id,
        )
        return

    safe_name = escape_markdown(file_data["file_name"])
    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"**Cᴏɴғɪʀᴍ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜᴇ Fɪʟᴇ**\n\n"
            f"📂 `{safe_name}`"
        ),
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("ʏᴇs", callback_data=f"msgdelpvtyes_{file_hash}"),
                InlineKeyboardButton("ɴᴏ",  callback_data=f"mainstream_{file_hash}"),
            ]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^(msgdelpvtyes_|mainstream_)"), group=2)
async def revoke_confirm_callback(client: Client, callback: CallbackQuery):
    if not await check_owner(client, callback):
        return

    data = callback.data

    if data.startswith("mainstream_"):
        file_hash = data[len("mainstream_"):]
        await callback.answer("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.", show_alert=False)
        try:
            await callback.message.edit_text(
                f"❌ **{small_caps('revoke cancelled')}.**"
            )
        except Exception:
            pass
        return

    if data.startswith("msgdelpvtyes_"):
        file_hash = data[len("msgdelpvtyes_"):]
        file_data = await db.get_file_by_hash(file_hash)

        if not file_data:
            await callback.answer("❌ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴅᴇʟᴇᴛᴇᴅ.", show_alert=True)
            return

        try:
            await client.delete_messages(Config.FLOG_CHAT_ID, int(file_data["message_id"]))
        except Exception as exc:
            logger.error("revoke delete dump message: msg=%s err=%s", file_data["message_id"], exc)

        await db.delete_file(file_data["message_id"])

        try:
            await callback.message.edit_text(
                f"🗑️ **{small_caps('file revoked successfully')}!**\n\n"
                f"📂 **{small_caps('file')}:** `{escape_markdown(file_data['file_name'])}`\n\n"
                "ᴀʟʟ ʟɪɴᴋꜱ ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ."
            )
        except Exception:
            pass
        await callback.answer("✅ ꜰɪʟᴇ ʀᴇᴠᴏᴋᴇᴅ!", show_alert=False)


@Client.on_message(filters.command("revokeall") & filters.private, group=2)
async def revokeall_command(client: Client, message: Message):
    if not await check_owner(client, message):
        return

    if len(message.command) > 1:
        raw = message.command[1]
        if not raw.lstrip("-").isdigit():
            await client.send_message(
                chat_id=message.chat.id,
                text=(
                    f"❌ **{small_caps('invalid user id')}**\n\n"
                    "ᴜꜱᴀɢᴇ: `/revokeall <user_id>`"
                ),
                reply_to_message_id=message.id,
            )
            return

        target_id = raw
        files     = await db.get_user_files(target_id, limit=0)
        count     = len(files)

        if count == 0:
            await client.send_message(
                chat_id=message.chat.id,
                text=f"📂 ɴᴏ ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ ꜰᴏʀ ᴜꜱᴇʀ `{target_id}`.",
                reply_to_message_id=message.id,
            )
            return

        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"**Cᴏɴғɪʀᴍ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜᴇ Fɪʟᴇ**\n\n"
                f"ᴛʜɪꜱ ᴡɪʟʟ ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ ᴅᴇʟᴇᴛᴇ **{count}** ꜰɪʟᴇꜱ "
                f"ʙᴇʟᴏɴɢɪɴɢ ᴛᴏ ᴜꜱᴇʀ `{target_id}`.\n"
                "ᴀʟʟ ꜱᴛʀᴇᴀᴍ/ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ ᴡɪʟʟ ʙᴇᴄᴏᴍᴇ ɪɴᴠᴀʟɪᴅ."
            ),
            reply_to_message_id=message.id,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ʏᴇs", callback_data=f"revokeuser_confirm_{target_id}"),
                    InlineKeyboardButton("ɴᴏ",  callback_data="revokeall_cancel"),
                ]
            ]),
        )
        return

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
            f"**Cᴏɴғɪʀᴍ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛʜᴇ Fɪʟᴇ**\n\n"
            f"ᴛʜɪꜱ ᴡɪʟʟ ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ ᴅᴇʟᴇᴛᴇ **{total_files}** ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴛʜᴇ ᴅᴀᴛᴀʙᴀꜱᴇ.\n"
            "ᴀʟʟ ꜱᴛʀᴇᴀᴍ/ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ ᴡɪʟʟ ʙᴇᴄᴏᴍᴇ ɪɴᴠᴀʟɪᴅ."
        ),
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("ʏᴇs", callback_data="revokeall_confirm"),
                InlineKeyboardButton("ɴᴏ",  callback_data="revokeall_cancel"),
            ]
        ]),
    )


@Client.on_callback_query(filters.regex(r"^revokeall_(confirm|cancel)$"), group=2)
async def revokeall_callback(client: Client, callback: CallbackQuery):
    if not await check_owner(client, callback):
        return

    if callback.data == "revokeall_cancel":
        await callback.answer("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.", show_alert=False)
        try:
            await callback.message.edit_text(f"❌ **{small_caps('revokeall cancelled')}.**")
        except Exception:
            pass
        return

    await callback.answer("🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ꜰɪʟᴇꜱ…", show_alert=False)
    try:
        await callback.message.edit_text("🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ꜰɪʟᴇꜱ…")
    except Exception:
        pass

    deleted_count = await db.delete_all_files()
    try:
        await callback.message.edit_text(
            f"🗑️ **{small_caps('all files deleted')}!**\n\n"
            f"ᴅᴇʟᴇᴛᴇᴅ `{deleted_count}` ꜰɪʟᴇꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ."
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^revokeuser_confirm_"), group=2)
async def revokeuser_confirm_callback(client: Client, callback: CallbackQuery):
    if not await check_owner(client, callback):
        return

    target_id = callback.data.replace("revokeuser_confirm_", "", 1)

    await callback.answer("🗑️ ᴅᴇʟᴇᴛɪɴɢ…", show_alert=False)
    try:
        await callback.message.edit_text(
            f"🗑️ ᴅᴇʟᴇᴛɪɴɢ ᴀʟʟ ꜰɪʟᴇꜱ ꜰᴏʀ ᴜꜱᴇʀ `{target_id}`…"
        )
    except Exception:
        pass

    deleted_count = await db.delete_user_files(target_id)
    try:
        await callback.message.edit_text(
            f"🗑️ **{small_caps('done')}!**\n\n"
            f"ᴅᴇʟᴇᴛᴇᴅ `{deleted_count}` ꜰɪʟᴇꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ "
            f"ꜰᴏʀ ᴜꜱᴇʀ `{target_id}`."
        )
    except Exception:
        pass


@Client.on_message(filters.command("logs") & filters.private, group=2)
async def logs_command(client: Client, message: Message):
    if not await check_owner(client, message):
        return

    log_file = "bot.log"

    if not os.path.isfile(log_file) or os.path.getsize(log_file) == 0:
        await client.send_message(
            chat_id=message.chat.id,
            text="❌ **Log file not found or empty.**",
            reply_to_message_id=message.id,
        )
        return

    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=log_file,
            file_name="bot.log",
            caption=(
                "📋 **Bot Logs**\n\n"
                f"📁 **File:** `bot.log`\n"
                f"📦 **Size:** `{human_size(os.path.getsize(log_file))}`"
            ),
            reply_to_message_id=message.id,
        )
    except Exception as exc:
        logger.error("logs_command send document error: %s", exc)
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                tail = fh.read()[-4000:]
            await client.send_message(
                chat_id=message.chat.id,
                text=f"📋 **Bot Logs** *(last 4 000 chars)*\n\n```\n{tail}\n```",
                reply_to_message_id=message.id,
            )
        except Exception as exc2:
            logger.error("logs_command fallback error: %s", exc2)
            await client.send_message(
                chat_id=message.chat.id,
                text=f"❌ **Error reading logs:** `{exc2}`",
                reply_to_message_id=message.id,
            )
