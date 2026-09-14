# -*- coding: utf-8 -*-
"""Tests for utils/validation.py - Input validation utilities."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.validation import (
    MAX_LENGTHS,
    validate_field_length,
    validate_input,
    sanitize_text,
    validate_email,
    validate_phone,
)


class TestValidateFieldLength:
    """Tests for validate_field_length function."""

    def test_none_value_returns_none(self):
        assert validate_field_length({}, "field") is None

    def test_non_string_value_returns_none(self):
        assert validate_field_length({"field": 123}, "field") is None

    def test_empty_string_required_returns_error(self):
        result = validate_field_length({"name": ""}, "name", required=True)
        assert result == "name is required"

    def test_whitespace_only_required_returns_error(self):
        result = validate_field_length({"name": "   "}, "name", required=True)
        assert result == "name is required"

    def test_valid_string_returns_none(self):
        assert validate_field_length({"name": "John"}, "name") is None

    def test_string_exceeding_max_len_returns_error(self):
        long_str = "a" * 201
        result = validate_field_length({"name": long_str}, "name")
        assert "exceeds maximum length" in result

    def test_custom_max_len(self):
        result = validate_field_length({"code": "ABCD"}, "code", max_len=3)
        assert "exceeds maximum length" in result

    def test_default_max_lengths(self):
        assert MAX_LENGTHS["name"] == 200
        assert MAX_LENGTHS["email"] == 254
        assert MAX_LENGTHS["phone"] == 50
        assert MAX_LENGTHS["description"] == 5000

    def test_unknown_field_uses_default_5000(self):
        long_str = "a" * 5001
        result = validate_field_length({"unknown": long_str}, "unknown")
        assert "exceeds maximum length" in result

    def test_at_limit_returns_none(self):
        at_limit = "a" * 200
        assert validate_field_length({"name": at_limit}, "name") is None


class TestValidateInput:
    """Tests for validate_input function."""

    def test_empty_rules_returns_none(self):
        assert validate_input({}, []) is None

    def test_string_rule(self):
        assert validate_input({"name": "OK"}, ["name"]) is None

    def test_tuple_rule_with_kwargs(self):
        data = {"name": ""}
        result = validate_input(data, [("name", {"required": True})])
        assert result is not None

    def test_first_error_returned(self):
        data = {"name": "a" * 201, "title": "OK"}
        result = validate_input(data, ["name", "title"])
        assert "name" in result

    def test_no_error_returns_none(self):
        data = {"name": "Valid", "title": "OK"}
        assert validate_input(data, ["name", "title"]) is None


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_none_returns_none(self):
        assert sanitize_text(None) is None

    def test_non_string_returns_value(self):
        assert sanitize_text(123) == 123

    def test_strips_whitespace(self):
        assert sanitize_text("  hello  ") == "hello"

    def test_truncates_to_max_len(self):
        result = sanitize_text("a" * 100, max_len=10)
        assert len(result) == 10

    def test_default_max_len(self):
        result = sanitize_text("a" * 6000)
        assert len(result) == 5000

    def test_empty_string(self):
        assert sanitize_text("") == ""


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_email(self):
        assert validate_email("test@example.com") is True

    def test_valid_email_with_subdomain(self):
        assert validate_email("user@mail.example.com") is True

    def test_valid_email_with_plus(self):
        assert validate_email("user+tag@example.com") is True

    def test_valid_email_with_dots(self):
        assert validate_email("first.last@example.com") is True

    def test_valid_email_with_numbers(self):
        assert validate_email("user123@example.com") is True

    def test_invalid_email_no_at(self):
        assert validate_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        assert validate_email("user@") is False

    def test_invalid_email_no_tld(self):
        assert validate_email("user@example") is False

    def test_invalid_email_empty(self):
        assert validate_email("") is False

    def test_invalid_email_none(self):
        assert validate_email(None) is False

    def test_invalid_email_not_string(self):
        assert validate_email(123) is False

    def test_valid_email_with_hyphen(self):
        assert validate_email("user-name@example.com") is True

    def test_valid_email_with_underscore(self):
        assert validate_email("user_name@example.com") is True


class TestValidatePhone:
    """Tests for validate_phone function."""

    def test_valid_phone_egypt(self):
        assert validate_phone("+201012345678") is True

    def test_valid_phone_ksa(self):
        assert validate_phone("+966501234567") is True

    def test_valid_phone_uae(self):
        assert validate_phone("+971501234567") is True

    def test_valid_phone_local_format(self):
        assert validate_phone("01012345678") is True

    def test_valid_phone_with_spaces(self):
        assert validate_phone("+20 101 234 5678") is True

    def test_valid_phone_with_dashes(self):
        assert validate_phone("+20-101-234-5678") is True

    def test_valid_phone_short(self):
        assert validate_phone("1234567") is True

    def test_invalid_phone_empty(self):
        assert validate_phone("") is False

    def test_invalid_phone_none(self):
        assert validate_phone(None) is False

    def test_invalid_phone_not_string(self):
        assert validate_phone(123) is False

    def test_invalid_phone_letters(self):
        assert validate_phone("+20abc1234567") is False

    def test_invalid_phone_too_short(self):
        assert validate_phone("123456") is False

    def test_invalid_phone_too_long(self):
        assert validate_phone("+2012345678901234") is False
