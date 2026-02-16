"""
Application constants and enums
"""

# File types
FILE_TYPE_VIDEO = "video"
FILE_TYPE_AUDIO = "audio"
FILE_TYPE_IMAGE = "image"
FILE_TYPE_DOCUMENT = "document"

STREAMABLE_TYPES = [FILE_TYPE_VIDEO, FILE_TYPE_AUDIO]

# MIME type mappings
MIME_TYPE_MAP = {
    FILE_TYPE_VIDEO: 'video/mp4',
    FILE_TYPE_AUDIO: 'audio/mpeg',
    FILE_TYPE_IMAGE: 'image/jpeg',
    FILE_TYPE_DOCUMENT: 'application/octet-stream'
}

# HTTP Status codes
HTTP_OK = 200
HTTP_PARTIAL_CONTENT = 206
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_REQUESTED_RANGE_NOT_SATISFIABLE = 416
HTTP_INTERNAL_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503

# Streaming configuration
DEFAULT_CHUNK_SIZE = 262144  # 256KB - optimal for streaming
RANGE_CHUNK_SIZE = 1048576  # 1MB - for range requests

# Cache headers
CACHE_CONTROL_PUBLIC = 'public, max-age=3600'
CACHE_CONTROL_NO_CACHE = 'no-cache, no-store, must-revalidate'
