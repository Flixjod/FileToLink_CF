from pyrogram import Client
from config import Config

# Bot client for handling bot commands
bot_client = Client(
    "filestream_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=50
)

# User client for downloading files (if needed)
user_client = None  # Can be initialized if needed for user bot functionality
