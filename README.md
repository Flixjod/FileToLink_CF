# 🎬 FileStream Bot - Python Version

A **high-performance** Telegram bot for file streaming and downloading with advanced bandwidth control, built with Python, Pyrogram, Flask, and MongoDB.

## ✨ Key Features & Optimizations

### 🚀 Performance Optimizations (NEW!)
- **⚡ Range Request Support**: Enables video seeking and resumable downloads
- **📦 Optimized Streaming**: 256KB chunk size for smooth playback
- **🔗 Connection Pooling**: MongoDB pool (10-50 connections) for faster queries
- **🗜️ Gzip Compression**: Automatic compression for JSON responses
- **💾 Telegram File ID Storage**: Direct file access without message parsing
- **🎯 Efficient Caching**: Smart caching with proper cache headers

### Core Features
- 📂 **File Streaming & Download**: Upload files to Telegram and get instant streaming/download links
- 🎬 **Media Player**: Beautiful embedded player for video and audio files
- 🔐 **Secure Links**: HMAC-SHA256 encrypted file links with revoke capability
- 💾 **MongoDB Storage**: Persistent storage with optimized indexes
- 📊 **Statistics Dashboard**: Real-time bot statistics on homepage
- 🎨 **Attractive UI**: Modern, responsive design with animations

### Advanced Features
- 📈 **Bandwidth Control**: 
  - Set bandwidth limits
  - Real-time bandwidth monitoring
  - Automatic blocking when limit reached
  - Daily and total bandwidth tracking
- 👥 **Access Control**:
  - Public/Private mode
  - Sudo user management
  - Owner-only commands
- 🔄 **File Management**:
  - View all your files
  - Revoke access to specific files
  - Delete all files (owner only)
- 🤖 **Bot Responses**: Small caps font styling for all responses
- 🐳 **Docker Support**: Easy deployment with Docker Compose

## 🏗️ Architecture Improvements

### New Project Structure
```
filestream-bot/
├── app.py                  # Main Flask application with optimizations
├── config.py              # Configuration (removed unnecessary webhook settings)
├── constants.py           # Application constants (NEW!)
├── bot/
│   ├── client.py          # Pyrogram client setup
│   └── handlers.py        # Bot command handlers (stores file_id, not filenames)
├── database/
│   └── mongodb.py         # Database with connection pooling
├── middlewares/           # Request middlewares (NEW!)
│   └── __init__.py        # Access control, bandwidth checking
├── services/              # Business logic layer (NEW!)
│   └── __init__.py        # StreamingService with range support
├── utils/
│   ├── crypto.py          # HMAC-SHA256 encryption
│   └── helpers.py         # Helper functions
└── templates/             # HTML templates
```

## 🚀 Installation

### Prerequisites
- Python 3.11+
- MongoDB 7.0+
- Telegram Bot Token (from @BotFather)
- Telegram API ID & API Hash (from https://my.telegram.org)

### Method 1: Docker (Recommended)

1. Clone the repository:
```bash
git clone <your-repo-url>
cd filestream-bot
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Edit `.env` with your configuration:
```bash
nano .env
```

4. Start with Docker Compose:
```bash
docker-compose up -d
```

### Method 2: Manual Installation

1. Clone and setup:
```bash
git clone <your-repo-url>
cd filestream-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
cp .env.example .env
nano .env
```

3. Start MongoDB:
```bash
# Install MongoDB if not already installed
# Then start it
mongod --dbpath /path/to/data
```

4. Run the bot:
```bash
python app.py
```

## ⚙️ Configuration

### Required Settings
```env
# Bot Configuration
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id_here
API_HASH=your_api_hash_here
BOT_OWNER=your_telegram_user_id
BOT_CHANNEL=your_channel_id  # Must be -100xxxxx format
OWNER_USERNAME=your_username
BOT_NAME=YourBotName

# MongoDB
MONGO_URI=mongodb://localhost:27017/
DATABASE_NAME=filestream_bot

# Security (HMAC signing for file links)
SECRET_KEY=your_powerful_secret_key_here

# Mode
PUBLIC_BOT=False  # Set True for public access

# Bandwidth (in bytes)
MAX_BANDWIDTH=107374182400  # 100GB

# Server
HOST=0.0.0.0
PORT=8080  # Cloud platforms (Heroku, Render) set this dynamically
BASE_URL=https://your-domain.com  # For generating download links (NOT webhooks!)
```

### Important Configuration Notes

#### Why No WEBHOOK_URL?
**Pyrogram uses long-polling (MTProto), NOT webhooks!** The `BASE_URL` is only used to generate download/stream links for users. Telegram bot updates are received via long-polling, which is more reliable and requires no webhook configuration.

#### Why PORT is Important?
Cloud platforms like Heroku, Render, and Railway assign ports dynamically via the `PORT` environment variable. The bot automatically uses this port, allowing flexible deployment across different platforms.

#### Bandwidth Examples
- 10GB = 10737418240
- 50GB = 53687091200
- 100GB = 107374182400
- 500GB = 536870912000

### Performance Tuning (Optional)
```env
# Streaming Performance
STREAM_CHUNK_SIZE=262144  # 256KB (default, optimal for most cases)
MAX_CONCURRENT_DOWNLOADS=10

# Cache Duration (seconds)
CACHE_DURATION=3600  # 1 hour
```

## 📋 Commands

### User Commands
- `/start` - Start the bot and show welcome message
- `/files` - View all your uploaded files
- `/revoke <token>` - Revoke a specific file using its secret token
- `/stats` - View bot statistics (files, users, downloads)
- `/bandwidth` - Check current bandwidth usage

### Owner Commands
- `/setpublic` - Toggle between public/private mode
- `/addsudo <user_id>` - Add a sudo user
- `/rmsudo <user_id>` - Remove a sudo user
- `/sudolist` - List all sudo users
- `/revokeall` - Delete all files (requires confirmation)
- `/confirmdelete` - Confirm deletion of all files
- `/setbandwidth <bytes>` - Set new bandwidth limit

## 🎯 Features Explained

### Performance Optimizations

#### 1. Range Request Support
- **Video Seeking**: Users can seek to any position in videos
- **Resumable Downloads**: Download can resume from where it stopped
- **Bandwidth Saving**: Only requested ranges are transferred
- **HTTP 206 Partial Content**: Standard-compliant implementation

#### 2. Connection Pooling
- **MongoDB**: Pool of 10-50 connections for optimal performance
- **Faster Queries**: Reduced connection overhead
- **Auto-scaling**: Adjusts based on load

#### 3. Telegram File ID Storage
- **Direct Access**: Use Telegram file_id for instant retrieval
- **No Message Parsing**: Eliminates need for channel info messages
- **Cleaner Channel**: Only file messages, no extra metadata messages
- **Faster Processing**: Direct file object access

#### 4. Streaming Optimizations
- **Optimal Chunk Size**: 256KB chunks for smooth streaming
- **Async Processing**: Non-blocking I/O operations
- **Smart Buffering**: Efficient memory usage

### Bandwidth Control System
The bot includes a sophisticated bandwidth monitoring system:

1. **Real-time Tracking**: Every download/stream is tracked
2. **Automatic Blocking**: When limit is reached, no more downloads allowed
3. **Statistics**: View daily and total bandwidth usage
4. **Owner Control**: Set custom bandwidth limits via command
5. **MongoDB Storage**: All bandwidth data stored persistently

### Access Control
- **Public Mode**: Anyone can use the bot
- **Private Mode**: Only owner and sudo users can use
- **Sudo Users**: Owner can add/remove users with special access
- **File Ownership**: Users can only revoke their own files (unless owner)

### File Security
- **HMAC-SHA256 Encryption**: Secure file link generation
- **Random Tokens**: Each file gets a unique secret token
- **Revoke System**: Delete files and links anytime
- **Expiration**: Links can be revoked to prevent further access

## 🌐 Deployment

### Koyeb / Render / Railway Deployment
1. Fork this repository
2. Connect to your platform
3. Set environment variables (especially `PORT` and `BASE_URL`)
4. Deploy!

**Note**: These platforms automatically set the `PORT` environment variable. The bot will use it automatically.

### VPS Deployment
1. Set up a VPS (Ubuntu 20.04+ recommended)
2. Install Docker and Docker Compose
3. Clone repository and configure
4. Run with Docker Compose
5. Set up Nginx reverse proxy (optional but recommended)

### Domain Setup
1. Point your domain to server IP
2. Update `BASE_URL` in `.env` with your domain
3. Restart the bot
4. (Optional) Set up SSL with Let's Encrypt

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│     Telegram Bot (Pyrogram)             │
│   - Long-polling (MTProto)              │
│   - File upload handling                │
│   - Command processing                  │
│   - Stores telegram_file_id             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       Flask Web Server                  │
│   - Range request support               │
│   - Optimized streaming                 │
│   - Gzip compression                    │
│   - Statistics API                      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      MongoDB Database                   │
│   - Connection pooling (10-50)          │
│   - Optimized indexes                   │
│   - File metadata + telegram_file_id    │
│   - Users & bandwidth tracking          │
└─────────────────────────────────────────┘
```

## 🔧 Troubleshooting

### Bot not responding
- Check if bot token is correct
- Verify bot is running: `docker-compose logs -f filestream_bot`
- Check MongoDB connection
- Ensure `BOT_CHANNEL` is in correct format (-100xxxxx)

### Files not streaming
- Verify `BASE_URL` is set correctly in `.env`
- Check if bandwidth limit is reached: `/bandwidth`
- Ensure file exists in channel
- Test with `/health` endpoint

### Video seeking not working
- Verify range request support is enabled (it's automatic)
- Check browser console for errors
- Ensure file size is correct in database

### Bandwidth issues
- Check current usage: `/bandwidth`
- View stats: `/stats`
- Adjust limit: `/setbandwidth <bytes>`

### Performance issues
- Monitor MongoDB connection pool
- Check chunk size configuration
- Verify network speed
- Review logs for bottlenecks

## 🆕 What's New in This Version

### Removed (Unnecessary for Pyrogram)
- ❌ `BOT_SECRET` - Not needed (webhooks use this, we use long-polling)
- ❌ Extra info messages in channel - Now stores file_id directly
- ❌ `WEBHOOK_URL` name - Renamed to `BASE_URL` for clarity

### Added
- ✅ Range request support for video streaming
- ✅ MongoDB connection pooling (10-50 connections)
- ✅ Gzip compression for JSON responses
- ✅ Telegram file_id storage for faster access
- ✅ Optimized chunk size (256KB)
- ✅ Better project structure (middlewares, services)
- ✅ Constants file for better maintainability
- ✅ Comprehensive error handling
- ✅ Performance logging

### Improved
- 🔄 Database queries with proper indexing
- 🔄 Streaming logic with async optimization
- 🔄 Configuration validation with helpful warnings
- 🔄 Code organization and separation of concerns

## 📝 License

This project is licensed under the MIT License.

## 🤝 Credits

- **Original Project**: [FileStream-CF](https://github.com/vauth/filestream-cf)
- **Python Version**: Converted and enhanced with performance optimizations
- **Libraries**: Pyrogram, Flask, Motor (MongoDB), Flask-Compress

## 👨‍💻 Developer

Created with ❤️ by [@FLiX_LY](https://t.me/FLiX_LY)

## ⚠️ Disclaimer

This bot is for educational purposes. Use responsibly and comply with Telegram's Terms of Service. The developers are not responsible for any misuse.

## 🆘 Support

For support, contact [@FLiX_LY](https://t.me/FLiX_LY) on Telegram.

---

**Star ⭐ this repo if you find it useful!**
