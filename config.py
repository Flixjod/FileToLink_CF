import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    API_ID = int(os.getenv('API_ID', 0))
    API_HASH = os.getenv('API_HASH')
    BOT_OWNER = int(os.getenv('BOT_OWNER', 0))
    BOT_CHANNEL = int(os.getenv('BOT_CHANNEL', 0))
    OWNER_USERNAME = os.getenv('OWNER_USERNAME', 'owner')
    BOT_NAME = os.getenv('BOT_NAME', 'FileStream Bot')
    
    # MongoDB Configuration
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'filestream_bot')
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-secret-key')
    BOT_SECRET = os.getenv('BOT_SECRET', 'change-this-bot-secret')
    
    # Mode Configuration
    PUBLIC_BOT = os.getenv('PUBLIC_BOT', 'False').lower() == 'true'
    
    # Bandwidth Control (in bytes)
    MAX_BANDWIDTH = int(os.getenv('MAX_BANDWIDTH', 107374182400))  # 100GB default
    
    # File Size Limits (in bytes)
    MAX_TELEGRAM_SIZE = int(os.getenv('MAX_TELEGRAM_SIZE', 4294967296))  # 4GB
    MAX_STREAM_SIZE = int(os.getenv('MAX_STREAM_SIZE', 2147483648))  # 2GB
    
    # Server Configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8080))
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
    
    # Cache Configuration
    CACHE_DURATION = int(os.getenv('CACHE_DURATION', 3600))
    
    @staticmethod
    def validate():
        """Validate required configuration"""
        required = ['BOT_TOKEN', 'API_ID', 'API_HASH', 'BOT_OWNER', 'BOT_CHANNEL']
        missing = [key for key in required if not getattr(Config, key)]
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
