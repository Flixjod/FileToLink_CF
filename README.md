# 🎬 FileStream Bot

A high-performance Telegram bot for file streaming and downloading, built with **Python**, **Pyrogram**, **aiohttp**, and **MongoDB**.

---

## ✨ Features

- **⚡ Range Request Support** — video seeking and resumable downloads
- **📦 Efficient Streaming** — 1 MB chunk size, aligned to Telegram's `upload.GetFile` limit
- **🔗 MongoDB Connection Pooling** — 10–50 connections for fast queries
- **💾 File ID Storage** — direct Telegram file access without re-downloading
- **🔐 Secure Links** — HMAC-SHA256 signed file hashes
- **📢 Log Channel** — new user registrations and file uploads logged automatically
- **⚙️ Settings Panel** — full bot configuration via inline keyboard (`/bot_settings`)
- **🐳 Docker Support** — ready-to-use `Dockerfile`

---

## 🏗️ Project Structure

```
filestream-bot/
├── main.py              # Entry point — boots bot + web server
├── app.py               # aiohttp web app (routes)
├── bot.py               # Pyrogram client
├── config.py            # Configuration + coloured logging setup
├── FLiX/
│   ├── __init__.py
│   ├── admin.py         # /bot_settings, /revokeall, /logs + callback handlers
│   ├── gen.py           # File handler, /files, /revoke, /stats
│   └── start.py         # /start, /help, /about
├── database/
│   └── mongodb.py       # Motor async MongoDB client
├── helper/
│   ├── __init__.py
│   ├── bandwidth.py     # Bandwidth check helper
│   ├── crypto.py        # HMAC hash utility
│   ├── stream.py        # ByteStreamer + StreamingService
│   └── utils.py         # format_size, escape_markdown, small_caps, check_fsub
└── templates/           # Jinja2 HTML templates
```

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- MongoDB 6.0+
- Telegram Bot Token — [@BotFather](https://t.me/BotFather)
- Telegram API ID & Hash — [my.telegram.org](https://my.telegram.org)

### Method 1 — Docker (Recommended)

```bash
git clone <your-repo-url>
cd filestream-bot
cp .env.example .env
# Edit .env with your values
docker build -t filestream-bot .
docker run -d --env-file .env filestream-bot
```

### Method 2 — Manual

```bash
git clone <your-repo-url>
cd filestream-bot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python main.py
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API Hash from my.telegram.org |
| `DUMP_CHAT_ID` | ✅ | Channel ID where files are stored |
| `OWNER_ID` | ✅ | Your Telegram user ID (comma-separated for multiple) |
| `DB_URI` | ✅ | MongoDB connection string |
| `DATABASE_NAME` | — | MongoDB database name (default: `filestream_bot`) |
| `URL` | — | Public base URL for stream/download links |
| `PORT` | — | Web server port (default: `8080`) |
| `LOGS_CHAT_ID` | — | Channel ID for logging new users & files |
| `SECRET_KEY` | — | HMAC secret for link signing |
| `Start_IMG` | — | URL of image shown with `/start` |
| `FSUB_ID` | — | Force-subscription channel ID |
| `FSUB_INV_LINK` | — | Invite link for force-subscription |
| `PUBLIC_BOT` | — | `True`/`False` — allow everyone (default: `False`) |
| `MAX_BANDWIDTH` | — | Bandwidth limit in bytes (default: 100 GB) |
| `MAX_TELEGRAM_SIZE` | — | Max accepted file size (default: 4 GB) |

> **Note:** `PUBLIC_BOT`, `MAX_BANDWIDTH`, bandwidth mode, force-sub settings, and sudo users are all managed live via `/bot_settings` and stored in MongoDB. The env variables above are **initial defaults** only.

---

## 🤖 Bot Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message & feature overview |
| `/help` | Usage guide |
| `/about` | Bot info |
| `/files` | View your uploaded files |
| `/stats` | Bot statistics |
| `/revoke <hash>` | Delete a specific file & invalidate its links |

### Owner Commands

| Command | Description |
|---|---|
| `/bot_settings` | Full settings panel (bandwidth, sudo, bot mode, force-sub) |
| `/revokeall` | Delete **all** files (shows confirm/cancel buttons) |
| `/logs` | Receive the full `bot.log` file as a document |

> All legacy text commands (`/addsudo`, `/rmsudo`, `/sudolist`, `/setpublic`, `/setbandwidth`, `/broadcast`, `/bandwidth`) have been removed in favour of the `/bot_settings` inline panel.

---

## 📋 Log Channel Events

When `LOGS_CHAT_ID` is set, the bot automatically posts:

- `#NewUser` — whenever a new user starts the bot
- `#NewFile` — whenever a file is uploaded (user, file name, size, type)

---

## 🌐 Web Endpoints

| Path | Description |
|---|---|
| `GET /` | Home page (static, no DB call) |
| `GET /stream/<hash>` | Inline media player or raw stream |
| `GET /dl/<hash>` | Force-download with `Content-Disposition: attachment` |
| `GET /stats` | JSON stats (files, users, bandwidth) |
| `GET /bandwidth` | JSON bandwidth details |
| `GET /health` | Health check |

---

## 📦 Dependencies

```
pyrogram
tgcrypto
motor
aiohttp
aiohttp-jinja2
jinja2
python-dotenv
```

---

## 👨‍💻 Developer

Built by [@FLiX_LY](https://t.me/FLiX_LY)
