import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration class with DB-backed dynamic settings"""
    _data = {}

    # Bot Configuration
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", "0"))
    API_HASH = os.environ.get("API_HASH", "")
    
    BOT_USERNAME = None
    
    # Owner IDs (supports multiple owners)
    OWNER_ID = list(
        {1008848605} | set(map(int, os.environ.get("OWNER_ID", "").split(",")))
        if os.environ.get("OWNER_ID") else {1008848605}
    )
    
    # Database Configuration
    DB_URI = os.environ.get("DB_URI", "mongodb://localhost:27017/")
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "filestream_bot")
    
    # Channel/Chat Configuration
    LOGS_CHAT_ID = int(os.environ.get("LOGS_CHAT_ID", "0"))
    DUMP_CHAT_ID = int(os.environ.get("DUMP_CHAT_ID", "0"))
    
    # Media Configuration
    Start_IMG = os.environ.get("Start_IMG", "")
    
    # Force Subscription
    FSUB_ID = int(os.environ.get("FSUB_ID", "") or 0)
    FSUB_INV_LINK = os.environ.get("FSUB_INV_LINK", "")
    
    # Security - HMAC signing for file links
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
    
    # Server Configuration
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8080))
    BASE_URL = os.environ.get('BASE_URL', os.environ.get('WEBHOOK_URL', ''))
    
    # Performance Configuration
    STREAM_CHUNK_SIZE = int(os.environ.get('STREAM_CHUNK_SIZE', 262144))  # 256KB
    MAX_CONCURRENT_DOWNLOADS = int(os.environ.get('MAX_CONCURRENT_DOWNLOADS', 10))
    
    # Bot Workers
    WORKERS = int(os.environ.get('WORKERS', 50))
    SLEEP_THRESHOLD = int(os.environ.get('SLEEP_THRESHOLD', 10))

    @classmethod
    async def load(cls, db):
        """Load settings from DB into memory"""
        doc = await db.config.find_one({"key": "Settings"})
        if not doc:
            logger.warning("⚠️ ᴄᴏɴꜰɪɢ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅʙ — ᴀᴘᴘʟʏɪɴɢ ꜰʀᴇꜱʜ ᴄᴏɴꜰɪɢ ᴠᴀʟᴜᴇꜱ")
            doc = {
                "key": "Settings",
                # Force Sub
                "fsub_mode": bool(cls.FSUB_ID),
                "fsub_chat_id": cls.FSUB_ID or 0,
                "fsub_inv_link": cls.FSUB_INV_LINK or "",
                # Bandwidth Control
                "max_bandwidth": int(os.environ.get('MAX_BANDWIDTH', 107374182400)),  # 100GB
                "bandwidth_used": 0,
                # Bot Mode
                "public_bot": os.environ.get('PUBLIC_BOT', 'False').lower() == 'true',
                # File Limits
                "max_telegram_size": int(os.environ.get('MAX_TELEGRAM_SIZE', 4294967296)),  # 4GB
                "max_stream_size": int(os.environ.get('MAX_STREAM_SIZE', 2147483648)),  # 2GB
            }
            await db.config.insert_one(doc)
            logger.info("✅ ᴄᴏɴꜰɪɢ ᴄʀᴇᴀᴛᴇᴅ & ꜰᴜʟʟʏ ᴛᴜɴᴇᴅ ɪɴ ᴅʙ")
        else:
            logger.info("📥 ᴄᴏɴꜰɪɢ ꜰᴏᴜɴᴅ & ᴇɴʜᴀɴᴄᴇᴅ ꜰᴏʀ ᴜꜱᴇ")

        cls._data = doc
        logger.info("✨ ᴄᴏɴꜰɪɢ ɪꜱ ʟɪᴠᴇ ᴀɴᴅ ᴛᴜɴᴇᴅ ᴛᴏ ᴘᴇʀꜰᴇᴄᴛɪᴏɴ")

    @classmethod
    async def update(cls, db, updates: dict):
        """Update both DB and memory cache"""
        cls._data.update(updates)
        await db.config.update_one(
            {"key": "Settings"},
            {"$set": updates},
            upsert=True
        )
        logger.info(f"✅ ᴄᴏɴꜰɪɢ ᴜᴘᴅᴀᴛᴇᴅ: {list(updates.keys())}")

    # ----- Accessors -----
    @classmethod
    def get(cls, key, default=None):
        """Get config value from memory"""
        return cls._data.get(key, default)

    @classmethod
    def all(cls):
        """Get all config values"""
        return cls._data

    @staticmethod
    def validate():
        """Validate required configuration"""
        required = ['BOT_TOKEN', 'API_ID', 'API_HASH', 'DUMP_CHAT_ID']
        missing = []
        
        if not Config.BOT_TOKEN:
            missing.append('BOT_TOKEN')
        if not Config.API_ID or Config.API_ID == 0:
            missing.append('API_ID')
        if not Config.API_HASH:
            missing.append('API_HASH')
        if not Config.DUMP_CHAT_ID or Config.DUMP_CHAT_ID == 0:
            missing.append('DUMP_CHAT_ID')
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        # Warn if BASE_URL is not set
        if not Config.BASE_URL:
            logger.warning("⚠️  Warning: BASE_URL not set. Download links will use localhost.")
        
        logger.info("✅ Configuration validated successfully")
        return True
