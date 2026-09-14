"""AES-256 encryption at rest for sensitive fields (client secrets, webhook secrets)."""
import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet


def _derive_key(passphrase: str) -> bytes:
    """Derive a Fernet-compatible key from a passphrase using SHA-256."""
    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_field(plaintext: Optional[str], secret_key: str) -> Optional[str]:
    """Encrypt a plaintext string using AES-256-Fernet.
    
    Args:
        plaintext: The string to encrypt.
        secret_key: The passphrase to derive the encryption key from.
        
    Returns:
        The encrypted string, or None/empty if input is empty.
    """
    if not plaintext:
        return plaintext
    key = _derive_key(secret_key)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: Optional[str], secret_key: str) -> Optional[str]:
    """Decrypt a ciphertext string using AES-256-Fernet.
    
    Args:
        ciphertext: The encrypted string to decrypt.
        secret_key: The passphrase to derive the decryption key from.
        
    Returns:
        The decrypted string, or None/empty if input is empty.
        
    Raises:
        cryptography.fernet.InvalidToken: If the ciphertext is invalid or
            the wrong secret_key is used.
    """
    if not ciphertext:
        return ciphertext
    key = _derive_key(secret_key)
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()


def rotate_encryption(plaintext: str, old_key: str, new_key: str) -> str:
    """Re-encrypt data with a new key (for key rotation).
    
    Args:
        plaintext: The already-decrypted data.
        old_key: The old passphrase (unused if data is already decrypted).
        new_key: The new passphrase to encrypt with.
        
    Returns:
        The re-encrypted string.
    """
    return encrypt_field(plaintext, new_key)
