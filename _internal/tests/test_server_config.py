# -*- coding: utf-8 -*-
"""Tests for server_config.py - Desktop server configuration."""
import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server_config import (
    DEFAULTS,
    load_config,
    save_config,
    get_port,
    get_https_port,
    is_https_enabled,
    get_access_password,
    hash_access_password,
    check_access_password,
    is_port_in_use,
)


class TestDefaults:
    """Tests for DEFAULTS constant."""

    def test_has_port(self):
        assert "port" in DEFAULTS

    def test_has_access_password(self):
        assert "access_password" in DEFAULTS

    def test_has_auto_start(self):
        assert "auto_start" in DEFAULTS

    def test_has_ai_providers(self):
        assert "ai_providers" in DEFAULTS

    def test_default_port_is_1000(self):
        assert DEFAULTS["port"] == 1000


class TestCheckAccessPassword:
    """Tests for check_access_password function."""

    def test_empty_stored_empty_plain(self):
        assert check_access_password("", "") is True

    def test_empty_stored_nonempty_plain(self):
        assert check_access_password("", "password") is False

    def test_nonempty_stored_empty_plain(self):
        assert check_access_password("hashed", "") is False

    def test_hashed_password(self):
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash("mypassword")
        assert check_access_password(hashed, "mypassword") is True
        assert check_access_password(hashed, "wrongpass") is False

    def test_plain_text_fallback(self):
        assert check_access_password("secret", "secret") is True
        assert check_access_password("secret", "wrong") is False


class TestHashAccessPassword:
    """Tests for hash_access_password function."""

    def test_returns_string(self):
        result = hash_access_password("test")
        assert isinstance(result, str)

    def test_different_inputs_different_hashes(self):
        h1 = hash_access_password("pass1")
        h2 = hash_access_password("pass2")
        assert h1 != h2

    def test_empty_string(self):
        result = hash_access_password("")
        assert isinstance(result, str)

    def test_none_string(self):
        result = hash_access_password(None)
        assert isinstance(result, str)


class TestIsPortInUse:
    """Tests for is_port_in_use function."""

    def test_invalid_port_returns_false(self):
        # Port 1 is unlikely to be in use
        assert is_port_in_use(1) is False


class TestLoadSaveConfig:
    """Tests for load_config and save_config with temp files."""

    def test_load_config_returns_defaults_on_missing_file(self, monkeypatch):
        import server_config
        monkeypatch.setattr(server_config, "CONFIG_FILE", "/nonexistent/config.json")
        cfg = load_config()
        assert cfg["port"] == DEFAULTS["port"]

    def test_save_and_load_roundtrip(self, monkeypatch, tmp_path):
        import server_config
        config_file = tmp_path / "test_config.json"
        monkeypatch.setattr(server_config, "CONFIG_FILE", str(config_file))
        monkeypatch.setattr(server_config, "CONFIG_DIR", str(tmp_path))

        test_cfg = {"port": 8080, "access_password": "test"}
        result = save_config(test_cfg)
        assert result is True

        loaded = load_config()
        assert loaded["port"] == 8080
        assert loaded["access_password"] == "test"

    def test_save_config_creates_directory(self, monkeypatch, tmp_path):
        import server_config
        nested_dir = tmp_path / "subdir"
        config_file = nested_dir / "config.json"
        monkeypatch.setattr(server_config, "CONFIG_FILE", str(config_file))
        monkeypatch.setattr(server_config, "CONFIG_DIR", str(nested_dir))

        result = save_config({"port": 9090})
        assert result is True
        assert config_file.exists()
