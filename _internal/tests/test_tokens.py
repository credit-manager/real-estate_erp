# -*- coding: utf-8 -*-
"""Tests for security/tokens.py - JWT token handling."""
import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["SECRET_KEY"] = "test-jwt-secret-key-for-unit-tests"

from security.tokens import (
    ACCESS_TTL,
    REFRESH_TTL,
    ALGORITHM,
    ISSUER,
    _secret,
    _utc_epoch,
    issue_token_pair,
    decode_token,
)


class TestConstants:
    """Tests for token constants."""

    def test_access_ttl_is_30_minutes(self):
        assert ACCESS_TTL == timedelta(minutes=30)

    def test_refresh_ttl_is_7_days(self):
        assert REFRESH_TTL == timedelta(days=7)

    def test_algorithm_is_hs256(self):
        assert ALGORITHM == "HS256"

    def test_issuer(self):
        assert ISSUER == "dynamicpro-control-center"


class TestSecret:
    """Tests for _secret function."""

    def test_returns_string(self):
        secret = _secret()
        assert isinstance(secret, str)

    def test_returns_non_empty(self):
        assert len(_secret()) > 0


class TestUtcEpoch:
    """Tests for _utc_epoch function."""

    def test_naive_datetime(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        epoch = _utc_epoch(dt)
        assert isinstance(epoch, int)
        assert epoch > 0

    def test_aware_datetime(self):
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epoch = _utc_epoch(dt)
        assert isinstance(epoch, int)

    def test_consistent_results(self):
        dt1 = datetime(2026, 6, 15, 10, 30, 0)
        dt2 = datetime(2026, 6, 15, 10, 30, 0)
        assert _utc_epoch(dt1) == _utc_epoch(dt2)


class TestIssueTokenPair:
    """Tests for issue_token_pair function."""

    def test_returns_three_values(self):
        result = issue_token_pair(1, "test@test.com", "Test", ["dashboard.view"])
        assert len(result) == 3

    def test_access_token_is_string(self):
        access, _, _ = issue_token_pair(1, "test@test.com", "Test", ["dashboard.view"])
        assert isinstance(access, str)
        assert len(access) > 50

    def test_refresh_token_is_string(self):
        _, refresh, _ = issue_token_pair(1, "test@test.com", "Test", ["dashboard.view"])
        assert isinstance(refresh, str)
        assert len(refresh) > 50

    def test_jti_is_string(self):
        _, _, jti = issue_token_pair(1, "test@test.com", "Test", ["dashboard.view"])
        assert isinstance(jti, str)
        assert len(jti) == 32  # uuid4 hex


class TestDecodeToken:
    """Tests for decode_token function."""

    def test_valid_access_token(self):
        access, _, _ = issue_token_pair(1, "a@b.com", "User", ["p1"])
        payload = decode_token(access, expected_type="access")
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["email"] == "a@b.com"
        assert payload["typ"] == "access"

    def test_valid_refresh_token(self):
        _, refresh, _ = issue_token_pair(1, "a@b.com", "User", ["p1"])
        payload = decode_token(refresh, expected_type="refresh")
        assert payload is not None
        assert payload["typ"] == "refresh"

    def test_wrong_type_returns_none(self):
        access, _, _ = issue_token_pair(1, "a@b.com", "User", ["p1"])
        payload = decode_token(access, expected_type="refresh")
        assert payload is None

    def test_invalid_token_returns_none(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_empty_token_returns_none(self):
        assert decode_token("") is None
        assert decode_token(None) is None

    def test_expired_token(self):
        from unittest.mock import patch
        import security.tokens as tokens_mod

        access, _, _ = issue_token_pair(1, "a@b.com", "User", ["p1"])
        with patch.object(tokens_mod, "ACCESS_TTL", timedelta(seconds=-1)):
            access2, _, _ = issue_token_pair(1, "a@b.com", "User", ["p1"])
        payload = decode_token(access2)
        assert payload is None

    def test_token_contains_permissions(self):
        access, _, _ = issue_token_pair(1, "a@b.com", "User", ["p1", "p2"])
        payload = decode_token(access)
        assert "perms" in payload
        assert "p1" in payload["perms"]
        assert "p2" in payload["perms"]
