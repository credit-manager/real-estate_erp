"""AES-256 encryption at rest for sensitive fields (client secrets, webhook secrets)."""
import base64
import hashlib
import os
from cryptography.fernet import Fernet


def _derive_key(passphrase):
    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_field(plaintext, secret_key):
    if not plaintext:
        return plaintext
    key = _derive_key(secret_key)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext, secret_key):
    if not ciphertext:
        return ciphertext
    key = _derive_key(secret_key)
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()
