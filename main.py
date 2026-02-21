import asyncio
import logging

from aiohttp import web

import logging_config
from bot import Bot
from config import Config
from database import Database, db_instance

logging_config.setup()
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("starting up")

    try:
        Config.validate()
    except ValueError as exc:
        logger.critical("config error: %s", exc)
        raise SystemExit(1) from exc

    database = Database(Config.DB_URI, Config.DATABASE_NAME)
    await database.init_db()
    db_instance.set(database)
    await Config.load(database.db)

    bot = Bot()
    await bot.start()
    bot_info = await bot.get_me()
    Config.BOT_USERNAME = bot_info.username
    logger.info("bot connected: @%s id=%s dc=%s", bot_info.username, bot_info.id, bot_info.dc_id)

    from app import build_app
    web_app = build_app(database)
    runner  = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, Config.BIND_ADDRESS, Config.PORT)
    await site.start()

    public_url = Config.URL or f"http://{Config.BIND_ADDRESS}:{Config.PORT}"
    logger.info("web server live at %s", public_url)
    logger.info("all services ready")

    try:
        await asyncio.Event().wait()
    finally:
        logger.info("shutting down")
        await runner.cleanup()
        await database.close()
        await bot.stop()
        logger.info("shutdown complete")


asyncio.run(main())
