import os
import time
import logging
import sys
from dotenv import load_dotenv

load_dotenv()


logger = logging.getLogger(__name__)

# Default bot identity constants
DEFAULT_BOT_NAME     = "Fɪʟᴇ Sᴛʀᴇᴀᴍ Bᴏᴛ"
DEFAULT_BOT_USERNAME = "FileStreamRo_Bot"


class Config:
    _data = {}

    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID    = int(os.environ.get("API_ID", "0"))
    API_HASH  = os.environ.get("API_HASH", "")

    # File-type constants used by app.py / stream.py
    FILE_TYPE_VIDEO    = "video"
    FILE_TYPE_AUDIO    = "audio"
    FILE_TYPE_IMAGE    = "image"
    FILE_TYPE_DOCUMENT = "document"

    BOT_USERNAME = DEFAULT_BOT_USERNAME  # fallback until bot.start() resolves real username
    BOT_NAME     = DEFAULT_BOT_NAME      # fallback until bot.start() resolves real name
    UPTIME: float = 0.0                  # set once at startup (epoch seconds)

    OWNER_ID = list(
        {1008848605} | set(map(int, os.environ.get("OWNER_ID", "").split(",")))
        if os.environ.get("OWNER_ID") else {1008848605}
    )

    DB_URI        = os.environ.get("DB_URI", "mongodb://localhost:27017/")
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "FileStream_New_bot")

    LOGS_CHAT_ID = int(os.environ.get("LOGS_CHAT_ID", "0"))

    # Renamed: DUMP_CHAT_ID → FLOG_CHAT_ID  (support legacy env var as fallback)
    FLOG_CHAT_ID = int(
        os.environ.get("FLOG_CHAT_ID")
        or os.environ.get("DUMP_CHAT_ID", "0")
    )
    # Keep alias for any code that still uses the old name during migration
    DUMP_CHAT_ID = FLOG_CHAT_ID

    Start_IMG = os.environ.get("Start_IMG", "")
    Files_IMG = os.environ.get("Files_IMG", "")

    FSUB_ID       = int(os.environ.get("FSUB_ID", "") or 0)
    FSUB_INV_LINK = os.environ.get("FSUB_INV_LINK", "")

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")

    BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
    PORT         = int(os.environ.get("PORT", 8080))
    URL          = os.environ.get("URL", os.environ.get("BASE_URL", ""))

    @classmethod
    async def load(cls, db):
        doc = await db.config.find_one({"key": "Settings"})
        if not doc:
            logger.warning("⚠️ ᴄᴏɴꜰɪɢ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅʙ — ᴀᴘᴘʟˏɪɴɢ ꜰʀᴇꜱʜ ᴄᴏɴꜰɪɢ ᴠᴀʟᴜᴇꜱ")
            doc = {
                "key":            "Settings",
                "fsub_mode":      bool(cls.FSUB_ID),
                "fsub_chat_id":   cls.FSUB_ID or 0,
                "fsub_inv_link":  cls.FSUB_INV_LINK or "",
                "bandwidth_mode": True,
                "max_bandwidth":  int(os.environ.get("MAX_BANDWIDTH", 107374182400)),
                "bandwidth_used": 0,
                "public_bot":     os.environ.get("PUBLIC_BOT", "False").lower() == "true",
                # Renamed: max_telegram_size → max_file_size
                "max_file_size":  int(os.environ.get("MAX_TELEGRAM_SIZE", 4294967296)),
            }
            await db.config.insert_one(doc)
            logger.info("✅ ᴄᴏɴꜰɪɢ ᴄʀᴇᴀᴛᴇᴅ & ꜰᴜʟʟˏ ᴛᴜɴᴇᴅ ɪɴ ᴅʙ")
        else:
            defaults = {
                "bandwidth_mode": True,
                "fsub_mode":      doc.get("fsub_mode", False),
                "fsub_chat_id":   doc.get("fsub_chat_id", 0),
                "fsub_inv_link":  doc.get("fsub_inv_link", ""),
            }
            # Migrate old key name max_telegram_size → max_file_size
            if "max_telegram_size" in doc and "max_file_size" not in doc:
                defaults["max_file_size"] = doc["max_telegram_size"]
            missing = {k: v for k, v in defaults.items() if k not in doc}
            if missing:
                await db.config.update_one(
                    {"key": "Settings"},
                    {"$set": missing},
                )
                doc.update(missing)
                logger.info("🔄 ᴄᴏɴꜰɪɢ ᴍɪɢʀᴀᴛᴇᴅ — ꜰɪᴇʟᴅꜱ ᴀᴅᴅᴇᴅ: %s", list(missing.keys()))
            logger.info("📥 ᴄᴏɴꜰɪɢ ꜰᴏᴜɴᴅ & ᴇɴʜᴀɴᴄᴇᴅ ꜰᴏʀ ᴜꜱᴇ")
        cls._data = doc
        logger.info("✨ ᴄᴏɴꜰɪɢ ɪꜱ ʟɪᴠᴇ ᴀɴᴅ ᴛᴜɴᴇᴅ ᴛᴏ ᴘᴇʀꜰᴇᴄᴛɪᴏɴ")

    @classmethod
    async def update(cls, db, updates: dict):
        cls._data.update(updates)
        await db.config.update_one(
            {"key": "Settings"},
            {"$set": updates},
            upsert=True,
        )

    @classmethod
    def get(cls, key, default=None):
        # Transparently redirect legacy key → new key
        if key == "max_telegram_size":
            key = "max_file_size"
        return cls._data.get(key, default)

    @classmethod
    def all(cls):
        return cls._data

    @staticmethod
    def validate():
        missing = []
        if not Config.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not Config.API_ID or Config.API_ID == 0:
            missing.append("API_ID")
        if not Config.API_HASH:
            missing.append("API_HASH")
        if not Config.FLOG_CHAT_ID or Config.FLOG_CHAT_ID == 0:
            missing.append("FLOG_CHAT_ID (or legacy DUMP_CHAT_ID)")
        if missing:
            raise ValueError(f"missing required configuration: {', '.join(missing)}")
        if not Config.URL:
            logger.warning("⚠️ ᴜʀʟ ɴᴏᴛ ꜱᴇᴛ — ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋꜱ ᴡɪʟʟ ᴜꜱᴇ ʟᴏᴄᴀʟʜᴏꜱᴛ")
        return True
