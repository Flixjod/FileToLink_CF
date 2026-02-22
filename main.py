import asyncio
import logging
import sys

from aiohttp import web

from bot import Bot
from app import build_app
from config import Config
from database import Database, db_instance


# Logging
class LoggingFormatter(logging.Formatter):
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREY   = "\033[38;5;245m"
    CYAN   = "\033[38;5;51m"
    GREEN  = "\033[38;5;82m"
    YELLOW = "\033[38;5;220m"
    RED    = "\033[38;5;196m"
    PURPLE = "\033[38;5;135m"

    LEVEL_STYLES = {
        logging.DEBUG:    (GREY,   "ᴅᴇʙᴜɢ  "),
        logging.INFO:     (CYAN,   "ɪɴꜰᴏ   "),
        logging.WARNING:  (YELLOW, "ᴡᴀʀɴ   "),
        logging.ERROR:    (RED,    "ᴇʀʀᴏʀ  "),
        logging.CRITICAL: (RED,    "ᴄʀɪᴛɪᴄ "),
    }

    def format(self, record: logging.LogRecord) -> str:
        color, label = self.LEVEL_STYLES.get(
            record.levelno, (self.GREY, "?      ")
        )
        ts    = self.formatTime(record, "%H:%M:%S")
        name  = record.name.split(".")[-1][:16].ljust(16)
        msg   = record.getMessage()
        return (
            f"{self.GREY}{ts}{self.RESET} "
            f"{self.BOLD}{color}{label}{self.RESET} "
            f"{self.PURPLE}{name}{self.RESET}  "
            f"{msg}"
        )


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # ── Console (coloured) ─────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(LoggingFormatter())
    root.addHandler(console)

    # ── File (plain, full debug) ───────────────────────────────────────
    file_h = logging.FileHandler("bot.log", encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    )
    root.addHandler(file_h)

    # ── Silence noisy third-party loggers ──────────────────────────────
    for noisy in (
        "pyrogram",
        "aiohttp",
        "aiohttp.access",
        "aiohttp.server",
        "motor",
        "pymongo",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("  🎬  ꜰʟɪx ꜰɪʟᴇ ꜱᴛʀᴇᴀᴍ ʙᴏᴛ  ʙᴏᴏᴛɪɴɢ ᴜᴘ…")

    #Config validation
    logger.info("🔍  ᴠᴀʟɪᴅᴀᴛɪɴɢ ᴄᴏɴꜰɪɢᴜʀᴀᴛɪᴏɴ…")
    try:
        Config.validate()
    except ValueError as exc:
        logger.critical("❌  ᴄᴏɴꜰɪɢ ᴇʀʀᴏʀ: %s", exc)
        raise SystemExit(1) from exc

    #Database
    logger.info("🗄️   ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ᴅᴀᴛᴀʙᴀꜱᴇ…")
    database = Database(Config.DB_URI, Config.DATABASE_NAME)
    await database.init_db()
    db_instance.set(database)
    await Config.load(database.db)
    logger.info("✅  ᴄᴏɴꜰɪɢ ᴄʀᴇᴀᴛᴇᴅ & ꜰᴜʟʟʏ ᴛᴜɴᴇᴅ ɪɴ ᴅʙ")

    #Bot
    logger.info("🤖  ᴄᴏɴɴᴇᴄᴛɪɴɢ ʙᴏᴛ ᴛᴏ ᴛᴇʟᴇɢʀᴀᴍ…")
    bot = Bot()
    await bot.start()
    bot_info = await bot.get_me()
    Config.BOT_USERNAME = bot_info.username
    logger.info(
        "✅  ʙᴏᴛ ᴄᴏɴɴᴇᴄᴛᴇᴅ  │  @%s  │  ɪᴅ: %s  │  ᴅᴄ: %s",
        bot_info.username,
        bot_info.id,
        bot_info.dc_id,
    )

    #Web Server
    logger.info("🌐  ꜱᴛᴀʀᴛɪɴɢ ᴡᴇʙ ꜱᴇʀᴠᴇʀ…")
    web_app = build_app(bot, database)
    runner  = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, Config.BIND_ADDRESS, Config.PORT)
    await site.start()

    public_url = Config.URL or f"http://{Config.BIND_ADDRESS}:{Config.PORT}"
    logger.info("✅  ᴡᴇʙ ꜱᴇʀᴠᴇʀ ʟɪᴠᴇ")
    logger.info("🔗  %s", public_url)
    logger.info(
        "🚀  ᴀʟʟ ꜱᴇʀᴠɪᴄᴇꜱ ʀᴇᴀᴅʏ  │  ʙᴏᴛ: @%s",
        bot_info.username,
    )

    # ── Run until interrupted ──────────────────────────────────────────
    try:
        await asyncio.Event().wait()
    finally:
        logger.info("🛑  ꜱʜᴜᴛᴛɪɴɢ ᴅᴏᴡɴ ᴡᴇʙ ꜱᴇʀᴠᴇʀ…")
        await runner.cleanup()
        logger.info("🛑  ᴄʟᴏꜱɪɴɢ ᴅᴀᴛᴀʙᴀꜱᴇ…")
        await database.close()
        logger.info("🛑  ꜱᴛᴏᴘᴘɪɴɢ ʙᴏᴛ…")
        await bot.stop()
        logger.info("✅  ꜱʜᴜᴛᴅᴏᴡɴ ᴄᴏᴍᴘʟᴇᴛᴇ")


asyncio.run(main())