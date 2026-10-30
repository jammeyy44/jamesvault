"""Reversible encryption for provider-account passwords (players must be able to view them again).

AES-256-GCM; key derived from PROVIDER_ACCOUNT_KEY (preferred) or SECRET_KEY. Rotate by re-encrypting rows.
"""
import base64
import hashlib

from Crypto.Cipher import AES
from flask import current_app
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


def _key():
    secret = current_app.config.get("PROVIDER_ACCOUNT_KEY") or current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"jamesvault-game-account:{secret}".encode()).digest()


def encrypt_secret(plain: str) -> str:
    cipher = AES.new(_key(), AES.MODE_GCM)
    ct, tag = cipher.encrypt_and_digest(plain.encode())
    return base64.b64encode(cipher.nonce + tag + ct).decode()


def decrypt_secret(token: str) -> str:
    raw = base64.b64decode(token)
    nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
    return AES.new(_key(), AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag).decode()


class EncryptedText(TypeDecorator):
    """Column type that encrypts on write and decrypts on read, so existing code keeps using plain strings.
    Values written before this type existed (no "enc:" prefix) are read as-is and encrypted on their next write."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return "enc:" + encrypt_secret(value)  # always encrypt: values read back are already decrypted plaintext

    def process_result_value(self, value, dialect):
        if value is not None and value.startswith("enc:"):
            return decrypt_secret(value[4:])
        return value
