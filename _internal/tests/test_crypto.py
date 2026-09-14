# -*- coding: utf-8 -*-
"""Tests for utils/crypto.py - AES-256 encryption utilities."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.crypto import encrypt_field, decrypt_field, _derive_key, rotate_encryption


class TestDeriveKey:
    """Tests for _derive_key function."""

    def test_returns_bytes(self):
        key = _derive_key("test-secret")
        assert isinstance(key, bytes)

    def test_deterministic(self):
        key1 = _derive_key("same-secret")
        key2 = _derive_key("same-secret")
        assert key1 == key2

    def test_different_secrets_different_keys(self):
        key1 = _derive_key("secret-1")
        key2 = _derive_key("secret-2")
        assert key1 != key2

    def test_key_length(self):
        key = _derive_key("any-secret")
        assert len(key) == 44  # base64-encoded 32 bytes


class TestEncryptDecrypt:
    """Tests for encrypt_field and decrypt_field functions."""

    SECRET = "my-secret-encryption-key"

    def test_round_trip(self):
        original = "Sensitive data here"
        encrypted = encrypt_field(original, self.SECRET)
        decrypted = decrypt_field(encrypted, self.SECRET)
        assert decrypted == original

    def test_encryption_is_not_plaintext(self):
        encrypted = encrypt_field("secret", self.SECRET)
        assert encrypted != "secret"
        assert len(encrypted) > 10

    def test_different_encryptions_of_same_text(self):
        enc1 = encrypt_field("same", self.SECRET)
        enc2 = encrypt_field("same", self.SECRET)
        # Fernet uses random IV, so encryptions should differ
        assert enc1 != enc2

    def test_different_keys_fail_decryption(self):
        encrypted = encrypt_field("data", "key-1")
        with pytest.raises(Exception):
            decrypt_field(encrypted, "key-2")

    def test_empty_plaintext_returns_empty(self):
        assert encrypt_field("", "key") == ""
        assert decrypt_field("", "key") == ""

    def test_none_plaintext_returns_none(self):
        assert encrypt_field(None, "key") is None
        assert decrypt_field(None, "key") is None

    def test_unicode_support(self):
        original = "بيانات عربية敏感数据"
        encrypted = encrypt_field(original, self.SECRET)
        decrypted = decrypt_field(encrypted, self.SECRET)
        assert decrypted == original

    def test_long_text(self):
        original = "A" * 10000
        encrypted = encrypt_field(original, self.SECRET)
        decrypted = decrypt_field(encrypted, self.SECRET)
        assert decrypted == original


class TestRotateEncryption:
    """Tests for rotate_encryption function."""

    def test_rotate_with_new_key(self):
        original = "Secret data to rotate"
        old_key = "old-secret-key"
        new_key = "new-secret-key"
        
        # Encrypt with old key
        encrypted = encrypt_field(original, old_key)
        
        # Rotate to new key
        re_encrypted = rotate_encryption(original, old_key, new_key)
        
        # Should be decryptable with new key
        decrypted = decrypt_field(re_encrypted, new_key)
        assert decrypted == original

    def test_rotate_different_from_original(self):
        original = "Data"
        old_key = "old"
        new_key = "new"
        
        encrypted = encrypt_field(original, old_key)
        re_encrypted = rotate_encryption(original, old_key, new_key)
        
        # Encrypted values should differ
        assert encrypted != re_encrypted

    def test_rotate_preserves_content(self):
        original = "بيانات عربية"
        re_encrypted = rotate_encryption(original, "old", "new")
        decrypted = decrypt_field(re_encrypted, "new")
        assert decrypted == original

    def test_rotate_empty_string(self):
        assert rotate_encryption("", "old", "new") == ""

    def test_rotate_none(self):
        assert rotate_encryption(None, "old", "new") is None
