import logging
from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeChat
from config import Config

logger = logging.getLogger(__name__)


class Bot(Client):

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
        await super().start()
        me = await self.get_me()
        Config.BOT_USERNAME = me.username
        logger.info("bot started: @%s id=%s workers=%s", me.username, me.id, Config.WORKERS)
        await self._set_commands()
        return me

    async def stop(self, *args):
        await super().stop()
        logger.info("bot stopped")

    async def _set_commands(self):
        user_commands = [
            BotCommand("start",     "Start the bot"),
            BotCommand("help",      "Get help info"),
            BotCommand("about",     "About this bot"),
            BotCommand("files",     "View your files"),
            BotCommand("stats",     "Bot statistics"),
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
            await self.set_bot_commands(user_commands)
            for owner_id in Config.OWNER_ID:
                try:
                    await self.set_bot_commands(
                        owner_commands,
                        scope=BotCommandScopeChat(chat_id=owner_id),
                    )
                except Exception as e:
                    logger.warning("could not set owner commands for %s: %s", owner_id, e)
            logger.info("bot commands registered")
        except Exception as e:
            logger.error("failed to register commands: %s", e)


bot = Bot()
