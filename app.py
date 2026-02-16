from flask import Flask, request, Response, render_template, jsonify, send_file
from pyrogram import idle
from bot import bot_client, setup_handlers
from database import Database
from utils import Cryptic, format_size
from config import Config
import asyncio
import logging
import threading
import requests
from io import BytesIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Global database instance
db = None
bot_me = None


async def init_app():
    """Initialize the application"""
    global db, bot_me
    
    try:
        # Validate config
        Config.validate()
        
        # Initialize database
        db = Database(Config.MONGO_URI, Config.DATABASE_NAME)
        await db.init_db()
        logger.info("Database initialized successfully")
        
        # Start bot
        await bot_client.start()
        bot_me = await bot_client.get_me()
        logger.info(f"Bot started: @{bot_me.username}")
        
        # Setup handlers
        setup_handlers(bot_client, db)
        logger.info("Bot handlers registered")
        
        return True
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return False


async def stop_app():
    """Stop the application"""
    global db
    
    try:
        if db:
            await db.close()
        await bot_client.stop()
        logger.info("Application stopped successfully")
    except Exception as e:
        logger.error(f"Stop error: {e}")


def run_bot():
    """Run the bot in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(init_app())
        loop.run_until_complete(idle())
    except KeyboardInterrupt:
        loop.run_until_complete(stop_app())
    finally:
        loop.close()


# Start bot in separate thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()


# ==================== ROUTES ====================

@app.route('/')
async def home():
    """Home page with bot statistics"""
    try:
        if not db:
            return "Bot is initializing...", 503
        
        stats = await db.get_stats()
        bot_username = bot_me.username if bot_me else "filestream_bot"
        
        return render_template('home.html',
                             bot_name=Config.BOT_NAME,
                             bot_username=bot_username,
                             owner_username=Config.OWNER_USERNAME,
                             total_files=stats['total_files'],
                             total_users=stats['total_users'],
                             total_downloads=stats['total_downloads'])
    except Exception as e:
        logger.error(f"Home page error: {e}")
        return f"Error loading page: {str(e)}", 500


@app.route('/streampage')
async def stream_page():
    """Streaming page with player"""
    file_hash = request.args.get('file')
    
    if not file_hash:
        return "Missing file parameter", 400
    
    try:
        message_id = Cryptic.dehash_file_id(file_hash)
        file_data = await db.get_file(message_id)
        
        if not file_data:
            return "File not found", 404
        
        # Check bandwidth limit
        stats = await db.get_bandwidth_stats()
        if stats["total_bandwidth"] >= Config.MAX_BANDWIDTH:
            return render_template('bandwidth_exceeded.html',
                                 bot_name=Config.BOT_NAME,
                                 owner_username=Config.OWNER_USERNAME), 503
        
        base_url = request.url_root.rstrip('/')
        stream_url = f"{base_url}/stream/{file_hash}"
        download_url = f"{base_url}/dl/{file_hash}"
        telegram_url = f"https://t.me/{bot_me.username}?start={file_hash}"
        
        file_type = 'video' if file_data['file_type'] == 'video' else \
                   'audio' if file_data['file_type'] == 'audio' else 'document'
        
        return render_template('stream.html',
                             bot_name=Config.BOT_NAME,
                             owner_username=Config.OWNER_USERNAME,
                             file_name=file_data['file_name'],
                             file_size=format_size(file_data['file_size']),
                             file_type=file_type,
                             downloads=file_data.get('downloads', 0),
                             stream_url=stream_url,
                             download_url=download_url,
                             telegram_url=telegram_url)
    
    except Exception as e:
        logger.error(f"Stream page error: {e}")
        return f"Error: {str(e)}", 500


@app.route('/stream/<file_hash>')
@app.route('/dl/<file_hash>')
async def stream_file(file_hash):
    """Stream or download file"""
    try:
        message_id = Cryptic.dehash_file_id(file_hash)
        file_data = await db.get_file(message_id)
        
        if not file_data:
            return jsonify({"error": "File not found"}), 404
        
        # Check bandwidth limit
        stats = await db.get_bandwidth_stats()
        if stats["total_bandwidth"] >= Config.MAX_BANDWIDTH:
            return jsonify({"error": "Bandwidth limit exceeded"}), 503
        
        # Get file from Telegram
        try:
            message = await bot_client.get_messages(Config.BOT_CHANNEL, int(message_id))
            
            if not message:
                return jsonify({"error": "File not found in channel"}), 404
            
            # Get file info
            if message.document:
                file = message.document
            elif message.video:
                file = message.video
            elif message.audio:
                file = message.audio
            elif message.photo:
                file = message.photo
            else:
                return jsonify({"error": "Unsupported file type"}), 400
            
            # Check file size limit
            if file_data['file_size'] > Config.MAX_STREAM_SIZE and '/stream/' in request.path:
                return jsonify({"error": "File too large for streaming"}), 413
            
            # Get file path from Telegram
            file_path = await bot_client.download_media(message, in_memory=True)
            
            if not file_path:
                return jsonify({"error": "Failed to download file"}), 500
            
            # Update download counter and bandwidth (async)
            asyncio.create_task(db.increment_downloads(message_id, file_data['file_size']))
            
            # Determine content disposition
            disposition = 'inline' if '/stream/' in request.path else 'attachment'
            
            # Stream the file
            def generate():
                if isinstance(file_path, BytesIO):
                    file_path.seek(0)
                    while True:
                        chunk = file_path.read(8192)
                        if not chunk:
                            break
                        yield chunk
                else:
                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            yield chunk
            
            # Get mime type
            mime_type = file_data.get('file_type', 'application/octet-stream')
            if mime_type in ['video', 'audio', 'image', 'document']:
                mime_map = {
                    'video': 'video/mp4',
                    'audio': 'audio/mpeg',
                    'image': 'image/jpeg',
                    'document': 'application/octet-stream'
                }
                mime_type = mime_map.get(mime_type, 'application/octet-stream')
            
            response = Response(generate(), mimetype=mime_type)
            response.headers['Content-Disposition'] = f'{disposition}; filename="{file_data["file_name"]}"'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            
            return response
            
        except Exception as e:
            logger.error(f"File download error: {e}")
            return jsonify({"error": f"Failed to retrieve file: {str(e)}"}), 500
    
    except ValueError as e:
        return jsonify({"error": "Invalid file hash"}), 400
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/stats')
async def stats():
    """Get bot statistics"""
    try:
        if not db:
            return jsonify({"error": "Database not initialized"}), 503
        
        stats = await db.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/bandwidth')
async def bandwidth():
    """Get bandwidth statistics"""
    try:
        if not db:
            return jsonify({"error": "Database not initialized"}), 503
        
        stats = await db.get_bandwidth_stats()
        stats['limit'] = Config.MAX_BANDWIDTH
        stats['remaining'] = Config.MAX_BANDWIDTH - stats['total_bandwidth']
        stats['percentage'] = (stats['total_bandwidth'] / Config.MAX_BANDWIDTH * 100) if Config.MAX_BANDWIDTH > 0 else 0
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Bandwidth error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "bot": "running" if bot_me else "initializing"})


if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=False)
