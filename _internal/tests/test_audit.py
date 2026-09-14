# -*- coding: utf-8 -*-
"""Tests for security/audit.py - Audit logging."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAuditRecord:
    """Tests for audit.record function."""

    def test_record_creates_entry(self, app, db_session):
        from security.audit import record
        from security.models import MasterAuditLog

        record(
            action="TEST_ACTION",
            master_user_id=1,
            master_user_email="test@test.com",
            resource_type="test",
            resource_id=1,
            ip="127.0.0.1",
            result="SUCCESS",
        )
        log_entry = MasterAuditLog.query.filter_by(action="TEST_ACTION").first()
        assert log_entry is not None
        assert log_entry.master_user_email == "test@test.com"
        assert log_entry.ip == "127.0.0.1"

    def test_record_with_old_new_values(self, app, db_session):
        from security.audit import record
        from security.models import MasterAuditLog

        record(
            action="TEST_UPDATE",
            old_value="old",
            new_value="new",
        )
        log_entry = MasterAuditLog.query.filter_by(action="TEST_UPDATE").first()
        assert log_entry is not None
        assert log_entry.old_value == "old"
        assert log_entry.new_value == "new"

    def test_record_truncates_long_values(self, app, db_session):
        from security.audit import record
        from security.models import MasterAuditLog

        long_value = "x" * 2000
        record(action="TEST_TRUNCATE", old_value=long_value)
        log_entry = MasterAuditLog.query.filter_by(action="TEST_TRUNCATE").first()
        assert len(log_entry.old_value) <= 1000

    def test_record_does_not_raise_on_failure(self, app, db_session):
        from security.audit import record
        # Should not raise even if there's an issue
        record(action="TEST_NO_RAISE")
