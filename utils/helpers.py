import secrets
import string


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size"""
    if bytes_size == 0:
        return '0 B'
    
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    k = 1024
    i = 0
    size = bytes_size
    
    while size >= k and i < len(sizes) - 1:
        size /= k
        i += 1
    
    return f"{size:.2f} {sizes[i]}"


def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    if not text:
        return 'Unknown File'
    
    # Replace backticks with single quotes to avoid markdown issues
    return text.replace('`', "'")


def generate_secret_token(length: int = 16) -> str:
    """Generate a random secret token"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def small_caps(text: str) -> str:
    """Convert text to small caps (Unicode small capitals)"""
    normal = "abcdefghijklmnopqrstuvwxyz"
    small_caps_chars = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ"
    
    result = []
    for char in text.lower():
        if char in normal:
            idx = normal.index(char)
            result.append(small_caps_chars[idx])
        else:
            result.append(char)
    
    return ''.join(result)
