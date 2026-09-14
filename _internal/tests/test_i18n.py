# -*- coding: utf-8 -*-
"""Tests for i18n.py - Internationalization."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from i18n import (
    DEFAULT_LANG,
    LANG_CODES,
    TRANSLATIONS,
    get_lang,
    make_t,
)


class TestConstants:
    """Tests for i18n constants."""

    def test_default_lang_is_arabic(self):
        assert DEFAULT_LANG == "ar"

    def test_lang_codes(self):
        assert "ar" in LANG_CODES
        assert "en" in LANG_CODES

    def test_translations_has_ar(self):
        assert "ar" in TRANSLATIONS

    def test_translations_has_en(self):
        assert "en" in TRANSLATIONS

    def test_ar_translations_is_dict(self):
        assert isinstance(TRANSLATIONS["ar"], dict)

    def test_en_translations_is_dict(self):
        assert isinstance(TRANSLATIONS["en"], dict)


class TestMakeT:
    """Tests for make_t function."""

    def test_returns_callable(self):
        t = make_t("ar")
        assert callable(t)

    def test_arabic_translation(self):
        t = make_t("ar")
        # Test that it returns the key if not found
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_english_translation(self):
        t = make_t("en")
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_fallback_to_key(self):
        t = make_t("ar")
        result = t("some.missing.key")
        assert result == "some.missing.key"

    def test_invalid_lang_raises_key_error(self):
        # make_t doesn't handle invalid languages - it raises KeyError
        t = make_t("invalid_lang")
        with pytest.raises(KeyError):
            t("test")
