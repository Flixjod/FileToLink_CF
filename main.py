"""
Main Entry Point - Runs both Bot and Flask App
"""
import asyncio
import threading
import logging
from bot import bot
from database import Database
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def init_bot():
    """Initialize bot and database"""
    global_db = None
    try:
        # Validate config
        Config.validate()
        
        # Initialize database
        from database import Database
        global_db = Database(Config.DB_URI, Config.DATABASE_NAME)
        await global_db.init_db()
        bot.db = global_db
        logger.info("✅ Database initialized")
        
        # Load config from database
        await Config.load(global_db.db)
        logger.info("✅ Config loaded from database")
        
        # Initialize Flask services with database
        from app import init_flask_services
        init_flask_services(global_db)
        
        # Start bot
        await bot.start()
        logger.info("✅ Bot started successfully")
        
        # Keep bot running
        from pyrogram import idle
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Bot initialization failed: {e}", exc_info=True)
        raise


def run_bot():
    """Run bot in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(init_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    finally:
        loop.close()


def run_flask():
    """Run Flask app in main thread"""
    from app import app
    
    logger.info(f"🚀 Starting Flask server on {Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=False)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🎬 FileStream Bot v2.0 - Starting...")
    logger.info("=" * 60)
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True, name="BotThread")
    bot_thread.start()
    logger.info("🤖 Bot thread started")
    
    # Small delay to let bot initialize
    import time
    time.sleep(3)
    
    # Run Flask in main thread
    try:
        run_flask()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        logger.info("👋 Goodbye!")
