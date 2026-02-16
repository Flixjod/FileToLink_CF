import hmac
import hashlib
import base64
import secrets
from config import Config


class Cryptic:
    """Cryptographic operations for file hash generation and verification"""
    
    @staticmethod
    def generate_random_token(length: int = 12) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)[:length]
    
    @staticmethod
    def hmac_sha256(message: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature"""
        key = secret.encode('utf-8')
        msg = message.encode('utf-8')
        signature = hmac.new(key, msg, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    @staticmethod
    def hash_file_id(message_id: str) -> str:
        """
        Generate secure hash: random_token + message_id + HMAC(random_token:message_id, secret)
        Format: randomToken.messageId.signature
        """
        random_token = Cryptic.generate_random_token(12)
        payload = f"{random_token}:{message_id}"
        signature = Cryptic.hmac_sha256(payload, Config.SECRET_KEY)
        return f"{random_token}.{message_id}.{signature[:32]}"
    
    @staticmethod
    def dehash_file_id(hashed: str) -> str:
        """
        Verify and extract message_id from hash
        Raises ValueError if hash is invalid
        """
        parts = hashed.split('.')
        if len(parts) != 3:
            raise ValueError('Invalid hash format')
        
        random_token, message_id, provided_signature = parts
        
        # Verify HMAC signature
        payload = f"{random_token}:{message_id}"
        expected_signature = Cryptic.hmac_sha256(payload, Config.SECRET_KEY)[:32]
        
        if provided_signature != expected_signature:
            raise ValueError('Invalid signature - hash verification failed')
        
        return message_id
