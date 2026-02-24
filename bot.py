from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeChat
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
        Config.BOT_USERNAME = me.username
        Config.BOT_NAME     = me.first_name
        logger.info("⚡  ʙᴏᴛ: @%s  │  ɴᴀᴍᴇ: %s  │  ɪᴅ: %s  │  ᴡᴏʀᴋᴇʀs: %s",
                    me.username, me.first_name, me.id, "50")
        await self._set_commands()
        return me

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
            BotCommand("adminstats",   "📊 ᴀᴅᴍɪɴ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ (ᴜᴘᴛɪᴍᴇ, ʙᴡ, ᴜꜱᴇʀꜱ, ꜰɪʟᴇꜱ)"),
            BotCommand("bot_settings", "⚙️ ʙᴏᴛ ꜱᴇᴛᴛɪɴɢꜱ ᴘᴀɴᴇʟ"),
            BotCommand("broadcast",    "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ"),
            BotCommand("revokeall",    "🗑️ ʀᴇᴠᴏᴋᴇ ᴀʟʟ ꜰɪʟᴇꜱ (ᴏʀ ʙʏ ᴜꜱᴇʀ ɪᴅ)"),
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


