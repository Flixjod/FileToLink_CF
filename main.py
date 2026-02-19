"""
Main Entry Point – async-native, aiohttp web server + Pyrogram bot
"""
import asyncio
import logging
from aiohttp import web
from pyrogram import idle

from bot import bot
from config import Config
from database import Database, db_instance

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def start_services():
    print()
    print("-------------------- Initializing Database ---------------------")
    # Validate env vars first
    Config.validate()

    database = Database(Config.DB_URI, Config.DATABASE_NAME)
    await database.init_db()

    # Expose globally so plugins can import it
    db_instance.set(database)

    await Config.load(database.db)
    print("------------------------------ DONE ------------------------------")
    print()
    print("-------------------- Initializing Telegram Bot --------------------")

    await bot.start()
    bot_info = await bot.get_me()
    Config.BOT_USERNAME = bot_info.username
    print("------------------------------ DONE ------------------------------")
    print()
    print("--------------------- Initializing Web Server ---------------------")

    from app import build_app
    web_app = build_app(database)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, Config.BIND_ADDRESS, Config.PORT)
    await site.start()
    print("------------------------------ DONE ------------------------------")
    print()
    print("------------------------- Service Started -------------------------")
    print("                        bot =>> {}".format(bot_info.first_name))
    if bot_info.dc_id:
        print("                        DC ID =>> {}".format(str(bot_info.dc_id)))
    print(" URL =>> {}".format(Config.URL or f"http://{Config.BIND_ADDRESS}:{Config.PORT}"))
    print("------------------------------------------------------------------")

    await idle()

    # ---- graceful shutdown ----
    await runner.cleanup()
    await bot.stop()
    await database.close()


if __name__ == "__main__":
    print("=" * 68)
    print("🎬  FileStream Bot – Starting …")
    print("=" * 68)
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        logger.info("🛑 Stopped by user")
    except Exception as exc:
        logger.exception(f"❌ Fatal error: {exc}")
    finally:
        logger.info("👋 Goodbye!")
