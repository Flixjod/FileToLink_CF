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
        Generate secure short hash: HMAC-SHA256 truncated to 24 hex chars.
        Format: 6891b4165eab4ca5917ce1e6 (24 characters)
        """
        payload = f"{message_id}:{Config.SECRET_KEY}"
        signature = hmac.new(
            Config.SECRET_KEY.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return signature[:24]

    @staticmethod
    def verify_hash(file_hash: str, message_id: str) -> bool:
        """Verify if hash matches the message_id"""
        try:
            expected = Cryptic.hash_file_id(message_id)
            return hmac.compare_digest(file_hash, expected)
        except Exception:
            return False

    @staticmethod
    def dehash_file_id(hashed: str) -> str:
        """
        Validate hash format. Actual file lookup must go through the database.
        Raises ValueError on bad format.
        """
        if not hashed or len(hashed) != 24:
            raise ValueError('Invalid hash format – must be 24 hex characters')
        try:
            int(hashed, 16)
        except ValueError:
            raise ValueError('Invalid hash format – must be hexadecimal')
        return hashed
