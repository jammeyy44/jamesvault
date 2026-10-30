"""Photos and videos in the live chat: what is accepted, how it is verified, and where it is stored.

The type is decided from the file's own first bytes, never from the file name or the browser's Content-Type. Files get random
names and are stored outside the web root; they are only served through an endpoint that checks the player owns the message.
"""
import os
import uuid

from flask import current_app

PHOTO_MAX = 5 * 1024 * 1024
VIDEO_MAX = 20 * 1024 * 1024           # also Telegram's limit for a bot to download a file
LARGE_UPLOAD_PATH = "/api/v1/chat/attachments"
# the largest request body any route may receive (the attachment route enforces the per-type limits above)
REQUEST_MAX = VIDEO_MAX + 1024 * 1024


def sniff(head: bytes):
    """(kind, extension, mime) from the first bytes of a file, or None when it is not an accepted photo or video."""
    if head.startswith(b"\xff\xd8\xff"):
        return "photo", "jpg", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "photo", "png", "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "photo", "webp", "image/webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return ("video", "mov", "video/quicktime") if brand == b"qt  " else ("video", "mp4", "video/mp4")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video", "webm", "video/webm"
    return None


def limit_for(kind: str) -> int:
    return PHOTO_MAX if kind == "photo" else VIDEO_MAX


def chat_dir() -> str:
    path = os.path.join(current_app.config["UPLOAD_DIR"], "chat")
    os.makedirs(path, exist_ok=True)
    return path


def save(data: bytes, ext: str) -> str:
    name = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(chat_dir(), name), "wb") as out:
        out.write(data)
    return name
