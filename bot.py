"""
Bot Client Initialization
"""
from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeChat
from config import Config
import logging

logger = logging.getLogger(__name__)


class Bot(Client):
    """Enhanced Bot Client with plugin system"""

    def __init__(self):
        super().__init__(
            name="FileStreamBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="FLiX"),
            workers=Config.WORKERS,
            sleep_threshold=Config.SLEEP_THRESHOLD,
        )

    async def start(self):
        """Start the bot"""
        await super().start()
        me = await self.get_me()
        Config.BOT_USERNAME = me.username
        logger.info(f"🤖 Bot started: @{me.username}")
        logger.info(f"👤 Bot ID:       {me.id}")
        logger.info(f"⚡ Workers:      {Config.WORKERS}")

        await self._set_commands()
        return me

    async def stop(self, *args):
        """Stop the bot"""
        await super().stop()
        logger.info("🛑 Bot stopped")

    async def _set_commands(self):
        """Register bot command list with Telegram"""
        user_commands = [
            BotCommand("start",     "Start the bot"),
            BotCommand("help",      "Get help information"),
            BotCommand("about",     "About this bot"),
            BotCommand("files",     "View your files"),
            BotCommand("stats",     "View bot statistics"),
            BotCommand("bandwidth", "Check bandwidth usage"),
        ]

        owner_commands = user_commands + [
            BotCommand("setpublic",    "Toggle public/private mode"),
            BotCommand("addsudo",      "Add sudo user"),
            BotCommand("rmsudo",       "Remove sudo user"),
            BotCommand("sudolist",     "List sudo users"),
            BotCommand("setbandwidth", "Set bandwidth limit"),
            BotCommand("setfsub",      "Toggle force subscription"),
            BotCommand("broadcast",    "Broadcast message"),
            BotCommand("revokeall",    "Delete all files"),
            BotCommand("logs",         "Get bot logs"),
        ]

        try:
            # Default commands for all users
            await self.set_bot_commands(user_commands)

            # Expanded commands for each owner
            for owner_id in Config.OWNER_ID:
                try:
                    await self.set_bot_commands(
                        owner_commands,
                        scope=BotCommandScopeChat(chat_id=owner_id),
                    )
                except Exception as e:
                    logger.warning(f"Could not set owner commands for {owner_id}: {e}")

            logger.info("✅ Bot commands registered")
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")


# Singleton instance used throughout the project
bot = Bot()
