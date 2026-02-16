# 🎬 FileStream Bot - Python Version

A powerful Telegram bot for file streaming and downloading with advanced bandwidth control, built with Python, Pyrogram, Flask, and MongoDB.

## ✨ Features

### Core Features
- 📂 **File Streaming & Download**: Upload files to Telegram and get instant streaming/download links
- 🎬 **Media Player**: Beautiful embedded player for video and audio files
- 🔐 **Secure Links**: HMAC-SHA256 encrypted file links with revoke capability
- 💾 **MongoDB Storage**: Persistent storage for file info, users, and bandwidth tracking
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

## 🚀 Installation

### Prerequisites
- Python 3.11+
- MongoDB 7.0+
- Telegram Bot Token
- Telegram API ID & API Hash

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

# Security
SECRET_KEY=your_powerful_secret_key_here
BOT_SECRET=your_bot_webhook_secret_here

# Mode
PUBLIC_BOT=False  # Set True for public access

# Bandwidth (in bytes)
MAX_BANDWIDTH=107374182400  # 100GB

# Server
HOST=0.0.0.0
PORT=8080
WEBHOOK_URL=https://your-domain.com
```

### Bandwidth Examples
- 10GB = 10737418240
- 50GB = 53687091200
- 100GB = 107374182400
- 500GB = 536870912000

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

### Koyeb / Render Deployment
1. Fork this repository
2. Connect to Koyeb/Render
3. Set environment variables
4. Deploy!

Note: These platforms have bandwidth limits, which is why we included bandwidth control.

### VPS Deployment
1. Set up a VPS (Ubuntu 20.04+ recommended)
2. Install Docker and Docker Compose
3. Clone repository and configure
4. Run with Docker Compose
5. Set up Nginx reverse proxy (optional)

### Domain Setup
1. Point your domain to server IP
2. Update `WEBHOOK_URL` in `.env`
3. Restart the bot

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│           Telegram Bot (Pyrogram)       │
│   - File upload handling                │
│   - Command processing                  │
│   - Inline queries                      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Flask Web Server                │
│   - File streaming                      │
│   - Download endpoints                  │
│   - Statistics API                      │
│   - Beautiful UI                        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        MongoDB Database                 │
│   - Files collection                    │
│   - Users collection                    │
│   - Bandwidth collection                │
│   - Sudo users collection               │
└─────────────────────────────────────────┘
```

## 🔧 Troubleshooting

### Bot not responding
- Check if bot token is correct
- Verify bot is running: `docker-compose logs -f filestream_bot`
- Check MongoDB connection

### Files not streaming
- Verify WEBHOOK_URL is set correctly
- Check if bandwidth limit is reached
- Ensure file exists in channel

### Bandwidth issues
- Check current usage: `/bandwidth`
- View stats: `/stats`
- Adjust limit: `/setbandwidth <bytes>`

## 📝 License

This project is licensed under the MIT License.

## 🤝 Credits

- **Original Project**: [FileStream-CF](https://github.com/vauth/filestream-cf)
- **Python Version**: Converted and enhanced with new features
- **Libraries**: Pyrogram, Flask, Motor (MongoDB), Aiogram

## 👨‍💻 Developer

Created with ❤️ by [@FLiX_LY](https://t.me/FLiX_LY)

## ⚠️ Disclaimer

This bot is for educational purposes. Use responsibly and comply with Telegram's Terms of Service. The developers are not responsible for any misuse.

## 🆘 Support

For support, contact [@FLiX_LY](https://t.me/FLiX_LY) on Telegram.

---

**Star ⭐ this repo if you find it useful!**
