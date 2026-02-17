from flask import Flask, request, Response, render_template, jsonify
from flask_compress import Compress  # For response compression
from bot import bot
from database import Database
from utils import Cryptic, format_size
from config import Config
from services import StreamingService
from middlewares import check_bandwidth_limit
from constants import *
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Enable gzip compression for better performance
compress = Compress()
compress.init_app(app)

# Global instances (will be initialized by main.py)
db = None
streaming_service = None


def init_flask_services(database: Database):
    """Initialize Flask services with database instance"""
    global db, streaming_service
    db = database
    streaming_service = StreamingService(bot, db)
    logger.info("✅ Flask services initialized")


# ==================== ROUTES ====================

@app.route('/')
async def home():
    """Home page with bot statistics"""
    try:
        if not db:
            return "Bot is initializing...", HTTP_SERVICE_UNAVAILABLE
        
        stats = await db.get_stats()
        bot_username = Config.BOT_USERNAME or "filestream_bot"
        
        return render_template('home.html',
                             bot_name="FileStream Bot",
                             bot_username=bot_username,
                             owner_username="FLiX_LY",
                             total_files=stats['total_files'],
                             total_users=stats['total_users'],
                             total_downloads=stats['total_downloads'])
    except Exception as e:
        logger.error(f"Home page error: {e}")
        return f"Error loading page: {str(e)}", HTTP_INTERNAL_ERROR


@app.route('/streampage')
async def stream_page():
    """Streaming page with player"""
    file_hash = request.args.get('file')
    
    if not file_hash:
        return "Missing file parameter", HTTP_BAD_REQUEST
    
    try:
        # Get file from database using hash
        file_data = await db.get_file_by_hash(file_hash)
        
        if not file_data:
            return "File not found", HTTP_NOT_FOUND
        
        # Check bandwidth limit
        allowed, stats = await check_bandwidth_limit(db)
        if not allowed:
            return render_template('bandwidth_exceeded.html',
                                 bot_name=Config.BOT_NAME,
                                 owner_username=Config.OWNER_USERNAME), HTTP_SERVICE_UNAVAILABLE
        
        base_url = request.url_root.rstrip('/')
        stream_url = f"{base_url}/stream/{file_hash}"
        download_url = f"{base_url}/dl/{file_hash}"
        telegram_url = f"https://t.me/{Config.BOT_USERNAME}?start={file_hash}"
        
        file_type = 'video' if file_data['file_type'] == FILE_TYPE_VIDEO else \
                   'audio' if file_data['file_type'] == FILE_TYPE_AUDIO else 'document'
        
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
        return f"Error: {str(e)}", HTTP_INTERNAL_ERROR


@app.route('/stream/<file_hash>')
async def stream_file(file_hash):
    """
    Stream file with range request support
    Optimized for video/audio streaming with seeking capability
    """
    if not streaming_service:
        return jsonify({"error": "Service not initialized"}), HTTP_SERVICE_UNAVAILABLE
    
    return await streaming_service.stream_file(file_hash, is_download=False)


@app.route('/dl/<file_hash>')
async def download_file(file_hash):
    """
    Download file with range request support
    Set Content-Disposition to attachment for downloading
    """
    if not streaming_service:
        return jsonify({"error": "Service not initialized"}), HTTP_SERVICE_UNAVAILABLE
    
    return await streaming_service.stream_file(file_hash, is_download=True)


@app.route('/stats')
async def stats():
    """Get bot statistics"""
    try:
        if not db:
            return jsonify({"error": "Database not initialized"}), HTTP_SERVICE_UNAVAILABLE
        
        stats = await db.get_stats()
        
        # Add formatted versions for better readability
        stats['formatted'] = {
            'total_bandwidth': format_size(stats['total_bandwidth']),
            'today_bandwidth': format_size(stats['today_bandwidth'])
        }
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), HTTP_INTERNAL_ERROR


@app.route('/bandwidth')
async def bandwidth():
    """Get bandwidth statistics"""
    try:
        if not db:
            return jsonify({"error": "Database not initialized"}), HTTP_SERVICE_UNAVAILABLE
        
        stats = await db.get_bandwidth_stats()
        stats['limit'] = Config.MAX_BANDWIDTH
        stats['remaining'] = Config.MAX_BANDWIDTH - stats['total_bandwidth']
        stats['percentage'] = (stats['total_bandwidth'] / Config.MAX_BANDWIDTH * 100) if Config.MAX_BANDWIDTH > 0 else 0
        
        # Add formatted versions
        stats['formatted'] = {
            'total_bandwidth': format_size(stats['total_bandwidth']),
            'today_bandwidth': format_size(stats['today_bandwidth']),
            'limit': format_size(Config.MAX_BANDWIDTH),
            'remaining': format_size(stats['remaining'])
        }
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Bandwidth error: {e}")
        return jsonify({"error": str(e)}), HTTP_INTERNAL_ERROR


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "bot": "running" if Config.BOT_USERNAME else "initializing",
        "bot_username": Config.BOT_USERNAME,
        "streaming_service": "ready" if streaming_service else "initializing"
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Not found"}), HTTP_NOT_FOUND


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), HTTP_INTERNAL_ERROR
