# -*- coding: utf-8 -*-
"""Tests for security/two_factor.py - TOTP 2FA."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTwoFactorImports:
    """Test that two_factor module can be imported."""

    def test_import(self):
        import security.two_factor as tf
        assert hasattr(tf, "enroll")
        assert hasattr(tf, "verify_code")
        assert hasattr(tf, "is_enabled")
        assert hasattr(tf, "disable")
        assert hasattr(tf, "generate_recovery_codes")
        assert hasattr(tf, "verify_recovery_code")

    def test_constants(self):
        import security.two_factor as tf
        assert tf.ISSUER == "ERP Control Center"
        assert tf.MFA_LOCK_SECONDS == 300

    def test_generate_secret_returns_string(self):
        import security.two_factor as tf
        secret = tf.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) == 32

    def test_provisioning_uri(self):
        import security.two_factor as tf
        uri = tf.provisioning_uri("test@example.com", "JBSWY3DPEHPK3PXP")
        assert "otpauth" in uri
        assert "test%40example.com" in uri or "test@example.com" in uri

    def test_is_enabled_returns_false_for_nonexistent_user(self, app, db_session):
        import security.two_factor as tf
        result = tf.is_enabled(99999)
        assert result is False

    def test_disable_returns_true(self, app, db_session):
        import security.two_factor as tf
        result = tf.disable(99999)
        assert result is True

    def test_verify_code_wrong_format(self, app, db_session):
        import security.two_factor as tf
        result = tf.verify_code(1, "abc")
        assert result is False

    def test_verify_code_too_short(self, app, db_session):
        import security.two_factor as tf
        result = tf.verify_code(1, "12345")
        assert result is False

    def test_verify_code_wrong_length(self, app, db_session):
        import security.two_factor as tf
        result = tf.verify_code(1, "1234567")
        assert result is False

    def test_generate_recovery_codes_no_mfa(self, app, db_session):
        import security.two_factor as tf
        codes = tf.generate_recovery_codes(99999)
        assert codes == []
