# -*- coding: utf-8 -*-
"""Tests for utils/passwords.py - Password policy and generation."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.passwords import (
    MIN_LENGTH,
    WEAK_PASSWORDS,
    validate_password,
    generate_strong_password,
    check_password_strength,
)


class TestValidatePassword:
    """Tests for validate_password function."""

    def test_too_short(self):
        ok, msg = validate_password("Ab1")
        assert ok is False
        assert "8 أحرف" in msg

    def test_exactly_min_length(self):
        ok, _ = validate_password("Abcdef12")
        assert ok is True

    def test_no_letters(self):
        ok, msg = validate_password("12345678")
        assert ok is False
        assert "حروف وأرقام" in msg

    def test_no_digits(self):
        ok, msg = validate_password("abcdefgh")
        assert ok is False
        assert "حروف وأرقام" in msg

    def test_weak_password_admin123(self):
        ok, msg = validate_password("admin123")
        assert ok is False
        assert "ضعيفة" in msg

    def test_weak_password_password(self):
        ok, msg = validate_password("password")
        assert ok is False

    def test_weak_passwords_list(self):
        for pw in WEAK_PASSWORDS:
            ok, _ = validate_password(pw)
            assert ok is False, f"Expected '{pw}' to be rejected"

    def test_strong_password(self):
        ok, _ = validate_password("MyStr0ng!Pass")
        assert ok is True

    def test_empty_string(self):
        ok, msg = validate_password("")
        assert ok is False
        assert "8 أحرف" in msg

    def test_none_password(self):
        ok, msg = validate_password(None)
        assert ok is False

    def test_with_special_chars(self):
        ok, _ = validate_password("Test@1234#")
        assert ok is True


class TestGenerateStrongPassword:
    """Tests for generate_strong_password function."""

    def test_default_length(self):
        pw = generate_strong_password()
        assert len(pw) == 14

    def test_custom_length(self):
        pw = generate_strong_password(length=20)
        assert len(pw) == 20

    def test_generated_password_is_valid(self):
        pw = generate_strong_password()
        ok, _ = validate_password(pw)
        assert ok is True

    def test_not_in_weak_list(self):
        pw = generate_strong_password()
        assert pw.lower() not in WEAK_PASSWORDS

    def test_minimum_length(self):
        pw = generate_strong_password(length=8)
        assert len(pw) == 8

    def test_multiple_generations_are_unique(self):
        passwords = {generate_strong_password() for _ in range(20)}
        assert len(passwords) == 20


class TestCheckPasswordStrength:
    """Tests for check_password_strength function."""

    def test_empty_password_returns_zero(self):
        assert check_password_strength("") == 0

    def test_none_password_returns_zero(self):
        assert check_password_strength(None) == 0

    def test_short_password_low_score(self):
        score = check_password_strength("ab1")
        assert score < 30

    def test_medium_password(self):
        score = check_password_strength("Abcdef1")
        assert 30 <= score < 60

    def test_strong_password(self):
        score = check_password_strength("MyStr0ng!Pass")
        assert score >= 70

    def test_very_strong_password(self):
        score = check_password_strength("MyV3ryStr0ng!P@ssw0rd")
        assert score >= 80

    def test_weak_password_zero_score(self):
        for pw in WEAK_PASSWORDS:
            score = check_password_strength(pw)
            assert score == 0, f"Expected '{pw}' to have score 0"

    def test_with_uppercase_bonus(self):
        score_lower = check_password_strength("abcdefg1")
        score_upper = check_password_strength("Abcdefg1")
        assert score_upper > score_lower

    def test_with_special_chars_bonus(self):
        score_basic = check_password_strength("Abcdefg1")
        score_special = check_password_strength("Abcdefg1!")
        assert score_special > score_basic

    def test_longer_password_bonus(self):
        score_short = check_password_strength("Abcdef1")
        score_long = check_password_strength("Abcdefghij1")
        assert score_long > score_short

    def test_max_score_is_100(self):
        score = check_password_strength("MyV3ryStr0ng!P@ssw0rd#2026")
        assert score <= 100
