import hmac
import hashlib
import secrets
from config import Config


class Cryptic:

    @staticmethod
    def hash_file_id(message_id: str) -> str:
        payload = f"{message_id}:{Config.SECRET_KEY}"
        signature = hmac.new(
            Config.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature[:24]

    @staticmethod
    def verify_hash(file_hash: str, message_id: str) -> bool:
        try:
            expected = Cryptic.hash_file_id(message_id)
            return hmac.compare_digest(file_hash, expected)
        except Exception:
            return False
