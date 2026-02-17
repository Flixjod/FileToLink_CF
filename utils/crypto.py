import hmac
import hashlib
import secrets
from config import Config


class Cryptic:
    """Cryptographic operations for file hash generation and verification"""
    
    @staticmethod
    def generate_random_token(length: int = 12) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)[:length]
    
    @staticmethod
    def hash_file_id(message_id: str) -> str:
        """
        Generate secure short hash: HMAC-SHA256 truncated to 24 chars (12 bytes hex)
        Format: 6891b4165eab4ca5917ce1e6 (24 characters)
        """
        # Combine message_id with secret for security
        payload = f"{message_id}:{Config.SECRET_KEY}"
        signature = hmac.new(
            Config.SECRET_KEY.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Take first 24 characters for short hash
        return signature[:24]
    
    @staticmethod
    def verify_hash(file_hash: str, message_id: str) -> bool:
        """Verify if hash matches the message_id"""
        try:
            expected_hash = Cryptic.hash_file_id(message_id)
            return file_hash == expected_hash
        except Exception:
            return False
    
    @staticmethod
    def dehash_file_id(hashed: str) -> str:
        """
        Cannot directly decode hash - must query database
        This method is kept for compatibility but now requires DB lookup
        Raises ValueError if hash is invalid format
        """
        if not hashed or len(hashed) != 24:
            raise ValueError('Invalid hash format - must be 24 characters')
        
        # Hash validation will be done by database lookup
        # This just validates format
        try:
            int(hashed, 16)  # Check if valid hex
        except ValueError:
            raise ValueError('Invalid hash format - must be hexadecimal')
        
        return hashed  # Return hash for DB lookup
