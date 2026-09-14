# -*- coding: utf-8 -*-
"""Tests for security/security_events.py - Security event logging."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSecurityEventModel:
    """Tests for SecurityEvent model."""

    def test_import(self):
        from security.models import SecurityEvent
        assert SecurityEvent is not None

    def test_tablename(self):
        from security.models import SecurityEvent
        assert SecurityEvent.__tablename__ == "security_events"

    def test_has_required_columns(self):
        from security.models import SecurityEvent
        columns = {c.name for c in SecurityEvent.__table__.columns}
        assert "id" in columns
        assert "event_type" in columns
        assert "severity" in columns

    def test_to_dict(self, app, db_session):
        from security.models import SecurityEvent
        event = SecurityEvent(
            event_type="login_success",
            master_user_email="test@test.com",
            ip="127.0.0.1",
            severity="info",
        )
        db_session.add(event)
        db_session.commit()
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["event_type"] == "login_success"
        assert d["severity"] == "info"
