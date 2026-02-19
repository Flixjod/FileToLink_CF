"""
Main Entry Point
────────────────
Starts the aiohttp web server inside Pyrogram's event loop using
bot.run() exclusively.  bot.start() / idle() / bot.stop() are NOT used.
"""
import asyncio
import logging

from aiohttp import web

from bot import bot
from config import Config
from database import Database, db_instance

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
#  Services that run inside bot.run()'s event loop
# ══════════════════════════════════════════════════════════════════════════
async def _run_services():
    """
    Called by bot.run() once the Pyrogram client is connected.
    Initialises DB, web server, then keeps the loop alive.
    """

    # ── Database ───────────────────────────────────────────────────────
    logger.info("Initialising database …")
    try:
        Config.validate()
    except ValueError as exc:
        logger.critical("Configuration error: %s", exc)
        raise SystemExit(1) from exc

    database = Database(Config.DB_URI, Config.DATABASE_NAME)
    await database.init_db()
    db_instance.set(database)
    await Config.load(database.db)
    logger.info("Database ready")

    # ── Bot identity ───────────────────────────────────────────────────
    bot_info = await bot.get_me()
    Config.BOT_USERNAME = bot_info.username
    logger.info(
        "Bot connected | name=%s id=%s dc=%s",
        bot_info.first_name,
        bot_info.id,
        bot_info.dc_id,
    )

    # ── Web server ─────────────────────────────────────────────────────
    logger.info("Initialising web server …")
    from app import build_app

    web_app = build_app(database)
    runner  = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, Config.BIND_ADDRESS, Config.PORT)
    await site.start()
    logger.info(
        "Web server listening | url=%s",
        Config.URL or f"http://{Config.BIND_ADDRESS}:{Config.PORT}",
    )

    logger.info(
        "All services started | bot=%s url=%s",
        bot_info.first_name,
        Config.URL or f"http://{Config.BIND_ADDRESS}:{Config.PORT}",
    )

    # ── Keep-alive ─────────────────────────────────────────────────────
    # bot.run() keeps the loop alive; we just yield control indefinitely
    # so the web-server and handlers remain active.
    try:
        await asyncio.Event().wait()
    finally:
        logger.info("Shutting down web server …")
        await runner.cleanup()
        logger.info("Shutting down database …")
        await database.close()
        logger.info("Shutdown complete")


# ══════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("FileStream Bot — starting")
    try:
        bot.run(_run_services())
    except KeyboardInterrupt:
        logger.info("Stopped by user (KeyboardInterrupt)")
    except Exception as exc:
        logger.exception("Fatal error during startup: %s", exc)
    finally:
        logger.info("Goodbye")
