import time
from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeChat
from pyrogram.enums import ChatMemberStatus
from config import Config
import logging

logger = logging.getLogger(__name__)


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="FileStreamBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="FLiX"),
            workers=50,
            sleep_threshold=10,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        Config.BOT_USERNAME = me.username  or Config.DEFAULT_BOT_USERNAME
        Config.BOT_NAME     = me.first_name or Config.DEFAULT_BOT_NAME
        Config.UPTIME       = time.time()
        logger.info("⚡  ʙᴏᴛ: @%s  │  ɴᴀᴍᴇ: %s  │  ɪᴅ: %s  │  ᴡᴏʀᴋᴇʀs: %s",
                    me.username, me.first_name, me.id, "50")

        # ── Resolve FLOG_CHAT_ID peer & verify channel / Manage Messages ─
        await self._check_flog_chat()

        await self._set_commands()
        return me

    async def _check_flog_chat(self):
        """
        1. Resolve the peer (get_chat) so Pyrogram caches it — fixes
           'PeerIdInvalid' errors that occur when only a bare int is used.
        2. Fetch the bot's own membership to verify it has the
           'Manage Messages' (delete_messages) right.
        Logs a critical warning to every OWNER if permission is missing.
        """
        chat_id = Config.FLOG_CHAT_ID
        if not chat_id:
            logger.warning("⚠️  FLOG_CHAT_ID ɪꜱ ɴᴏᴛ ꜱᴇᴛ — ꜰɪʟᴇ ʟᴏɢɢɪɴɢ ᴅɪꜱᴀʙʟᴇᴅ")
            return

        # ── Step 1: resolve peer (caches access hash) ─────────────────────
        try:
            chat = await self.get_chat(chat_id)
            logger.info(
                "✅  ꜰʟᴏɢ ᴄʜᴀᴛ ʀᴇꜱᴏʟᴠᴇᴅ  │  ɴᴀᴍᴇ: \"%s\"  │  ɪᴅ: %s",
                getattr(chat, "title", None) or getattr(chat, "first_name", "?"),
                chat_id,
            )
        except Exception as exc:
            logger.critical(
                "❌  ᴄᴀɴɴᴏᴛ ʀᴇꜱᴏʟᴠᴇ FLOG_CHAT_ID=%s: %s  "
                "— ᴄʜᴇᴄᴋ ᴛʜᴀᴛ ᴛʜᴇ ʙᴏᴛ ɪꜱ ᴀ ᴍᴇᴍʙᴇʀ ᴏꜰ ᴛʜᴀᴛ ᴄʜᴀᴛ",
                chat_id, exc,
            )
            return

        # ── Step 2: check bot's own privileges ────────────────────────────
        try:
            me     = await self.get_me()
            member = await self.get_chat_member(chat_id, me.id)

            has_manage = False
            if member.status in (ChatMemberStatus.OWNER,):
                has_manage = True
            elif member.status == ChatMemberStatus.ADMINISTRATOR:
                privileges = getattr(member, "privileges", None)
                # 'delete_messages' maps to Manage Messages in Telegram
                has_manage = bool(privileges and privileges.can_delete_messages)

            if not has_manage:
                warn_text = (
                    "❌ Mɪꜱꜱɪɴɢ Pᴇʀᴍɪꜱꜱɪᴏɴ!\n\n"
                    "📝 Pʟᴇᴀꜱᴇ ɢʀᴀɴᴛ:\n"
                    "⚡ `Mᴀɴᴀɢᴇ Mᴇꜱꜱᴀɢᴇꜱ` ʀɪɢʜᴛ"
                )
                logger.critical(
                    "❌  ʙᴏᴛ ʟᴀᴄᴋꜱ 'Mᴀɴᴀɢᴇ Mᴇꜱꜱᴀɢᴇꜱ' ɪɴ FLOG chat %s  "
                    "— ꜱᴛʀᴇᴀᴍɪɴɢ ᴀɴᴅ ꜰɪʟᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴡɪʟʟ ꜰᴀɪʟ",
                    chat_id,
                )
                for owner_id in Config.OWNER_ID:
                    try:
                        await self.send_message(
                            chat_id=owner_id,
                            text=(
                                f"⚠️ **Fʟɪx Bᴏᴛ Pᴇʀᴍɪꜱꜱɪᴏɴ Wᴀʀɴɪɴɢ**\n\n"
                                f"🗂️ **Fʟᴏɢ Cʜᴀᴛ:** `{chat_id}`\n\n"
                                + warn_text
                            ),
                            disable_web_page_preview=True,
                        )
                    except Exception as notify_exc:
                        logger.warning(
                            "ᴄᴏᴜʟᴅ ɴᴏᴛ ɴᴏᴛɪꜰʏ ᴏᴡɴᴇʀ %s: %s",
                            owner_id, notify_exc,
                        )
            else:
                logger.info(
                    "✅  ʙᴏᴛ ʜᴀꜱ 'Mᴀɴᴀɢᴇ Mᴇꜱꜱᴀɢᴇꜱ' ɪɴ FLOG chat %s",
                    chat_id,
                )

        except Exception as exc:
            logger.warning(
                "⚠️  ᴄᴏᴜʟᴅ ɴᴏᴛ ᴄʜᴇᴄᴋ ʙᴏᴛ ᴘᴇʀᴍɪꜱꜱɪᴏɴꜱ ɪɴ FLOG chat %s: %s",
                chat_id, exc,
            )

    async def stop(self, *args):
        await super().stop()
        logger.info("🛑  ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ")

    async def _set_commands(self):
        user_commands = [
            BotCommand("start",     "🚀 ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
            BotCommand("help",      "📚 ɢᴇᴛ ʜᴇʟᴘ ɪɴꜰᴏ"),
            BotCommand("about",     "ℹ️ ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ"),
            BotCommand("files",     "📂 ᴠɪᴇᴡ ʏᴏᴜʀ ꜰɪʟᴇꜱ"),
        ]

        owner_commands = user_commands + [
            BotCommand("adminstats",   "🔐 ᴀᴅᴍɪɴ ꜱᴛᴀᴛꜱ (ᴜᴘᴛɪᴍᴇ, ʙᴡ, ᴜꜱᴇʀꜱ, ꜰɪʟᴇꜱ)"),
            BotCommand("bot_settings", "⚙️ ʙᴏᴛ ꜱᴇᴛᴛɪɴɢꜱ ᴘᴀɴᴇʟ"),
            BotCommand("broadcast",    "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ"),
            BotCommand("revoke",       "🗑️ ʀᴇᴠᴏᴋᴇ ꜰɪʟᴇ ʙʏ ʜᴀꜱʜ"),
            BotCommand("revokeall",    "🗑️ ʙᴜʟᴋ ʀᴇᴠᴏᴋᴇ [ᴀʟʟ | ᴜꜱᴇʀ_ɪᴅ]"),
            BotCommand("logs",         "📄 ɢᴇᴛ ʙᴏᴛ ʟᴏɢꜱ"),
        ]

        try:
            await self.set_bot_commands(user_commands)

            for owner_id in Config.OWNER_ID:
                try:
                    await self.set_bot_commands(
                        owner_commands,
                        scope=BotCommandScopeChat(chat_id=owner_id),
                    )
                except Exception as e:
                    logger.warning(
                        "⚠️  ᴄᴏᴜʟᴅ ɴᴏᴛ ꜱᴇᴛ ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅꜱ ꜰᴏʀ %s: %s",
                        owner_id, e,
                    )

            logger.info("✅  ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅꜱ ʀᴇɢɪꜱᴛᴇʀᴇᴅ")
        except Exception as e:
            logger.error("❌  ꜰᴀɪʟᴇᴅ ᴛᴏ ʀᴇɢɪꜱᴛᴇʀ ᴄᴏᴍᴍᴀɴᴅꜱ: %s", e)


