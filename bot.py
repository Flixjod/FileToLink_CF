"""
Bot Client Initialization
"""
from pyrogram import Client
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
            sleep_threshold=Config.SLEEP_THRESHOLD
        )
        self.db = None


def create_stream_client() -> Client:
    """Create a lightweight client for streaming (no updates)."""
    return Client(
        name="FileStreamStream",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        workers=1,
        sleep_threshold=Config.SLEEP_THRESHOLD,
        no_updates=True
    )
        
    async def start(self):
        """Start the bot"""
        await super().start()
        me = await self.get_me()
        Config.BOT_USERNAME = me.username
        logger.info(f"🤖 Bot started: @{me.username}")
        logger.info(f"👤 Bot ID: {me.id}")
        logger.info(f"⚡ Workers: {Config.WORKERS}")
        
        # Set bot commands
        await self.set_bot_commands()
        
        return me
    
    async def stop(self, *args):
        """Stop the bot"""
        await super().stop()
        logger.info("🛑 Bot stopped")
    
    async def set_bot_commands(self):
        """Set bot commands for better UX"""
        from pyrogram.types import BotCommand
        
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help information"),
            BotCommand("about", "About this bot"),
            BotCommand("files", "View your files"),
            BotCommand("stats", "View bot statistics"),
            BotCommand("bandwidth", "Check bandwidth usage"),
        ]
        
        # Add owner commands
        owner_commands = commands + [
            BotCommand("setpublic", "Toggle public/private mode"),
            BotCommand("addsudo", "Add sudo user"),
            BotCommand("rmsudo", "Remove sudo user"),
            BotCommand("sudolist", "List sudo users"),
            BotCommand("setbandwidth", "Set bandwidth limit"),
            BotCommand("broadcast", "Broadcast message"),
            BotCommand("logs", "Get bot logs"),
        ]
        
        try:
            # Set commands for all users
            await self.set_bot_commands(commands)
            
            # Set commands for owners
            from pyrogram.types import BotCommandScopeChat
            for owner_id in Config.OWNER_ID:
                try:
                    await self.set_bot_commands(
                        owner_commands,
                        scope=BotCommandScopeChat(chat_id=owner_id)
                    )
                except Exception as e:
                    logger.warning(f"Could not set commands for owner {owner_id}: {e}")
            
            logger.info("✅ Bot commands set successfully")
        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")


# Initialize bot instance
bot = Bot()
