"""
Security utilities for encryption and authentication.
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


def _get_fernet_key() -> bytes:
    """
    Derive a Fernet-compatible key from a secret.
    In production, this should be stored securely (e.g., AWS Secrets Manager).
    """
    secret = os.getenv("ENCRYPTION_SECRET", "thesis-formatter-secret-key-change-in-production")
    salt = b"thesis-formatter-salt"  # In production, use a random salt stored securely
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_fernet_key())
    return _fernet


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage.

    Args:
        api_key: The plaintext API key to encrypt.

    Returns:
        Encrypted API key as a base64 string.
    """
    if not api_key:
        return ""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an encrypted API key.

    Args:
        encrypted_key: The encrypted API key as a base64 string.

    Returns:
        The decrypted plaintext API key.
    """
    if not encrypted_key:
        return ""
    fernet = _get_fernet()
    encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
    return fernet.decrypt(encrypted).decode()
