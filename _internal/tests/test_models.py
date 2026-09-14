# -*- coding: utf-8 -*-
"""Tests for models - Database model structure and to_dict methods."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestUserModel:
    """Tests for User model."""

    def test_import(self):
        from models.user import User
        assert User is not None

    def test_tablename(self):
        from models.user import User
        assert User.__tablename__ == "users"

    def test_has_required_columns(self):
        from models.user import User
        columns = {c.name for c in User.__table__.columns}
        assert "id" in columns
        assert "username" in columns
        assert "email" in columns
        assert "password_hash" in columns
        assert "role" in columns
        assert "is_active" in columns


class TestRoleModel:
    """Tests for Role model."""

    def test_import(self):
        from models.role import Role
        assert Role is not None

    def test_tablename(self):
        from models.role import Role
        assert Role.__tablename__ == "roles"

    def test_has_permissions_json(self):
        from models.role import Role
        columns = {c.name for c in Role.__table__.columns}
        assert "permissions" in columns


class TestSecurityModels:
    """Tests for security models."""

    def test_master_role_import(self):
        from security.models import MasterRole
        assert MasterRole is not None

    def test_master_permission_import(self):
        from security.models import MasterPermission
        assert MasterPermission is not None

    def test_master_session_import(self):
        from security.models import MasterSession
        assert MasterSession is not None

    def test_master_two_factor_import(self):
        from security.models import MasterTwoFactor
        assert MasterTwoFactor is not None

    def test_master_audit_log_import(self):
        from security.models import MasterAuditLog
        assert MasterAuditLog is not None

    def test_module_catalog_import(self):
        from security.models import ModuleCatalog
        assert ModuleCatalog is not None

    def test_security_event_import(self):
        from security.models import SecurityEvent
        assert SecurityEvent is not None


class TestMasterRoleToDict:
    """Tests for MasterRole.to_dict method."""

    def test_to_dict_returns_dict(self, app, db_session):
        from security.models import MasterRole
        role = MasterRole(name="test_role", description="Test", is_system=False)
        db_session.add(role)
        db_session.commit()
        d = role.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "test_role"
        assert d["description"] == "Test"
        assert d["is_system"] is False


class TestMasterPermissionToDict:
    """Tests for MasterPermission.to_dict method."""

    def test_to_dict_returns_dict(self, app, db_session):
        from security.models import MasterPermission
        perm = MasterPermission(code="test.view", description="Test view")
        db_session.add(perm)
        db_session.commit()
        d = perm.to_dict()
        assert isinstance(d, dict)
        assert d["code"] == "test.view"


class TestMasterAuditLogToDict:
    """Tests for MasterAuditLog.to_dict method."""

    def test_to_dict_returns_dict(self, app, db_session):
        from security.models import MasterAuditLog
        log = MasterAuditLog(
            action="TEST_ACTION",
            master_user_email="test@test.com",
            resource_type="test",
            result="SUCCESS",
        )
        db_session.add(log)
        db_session.commit()
        d = log.to_dict()
        assert isinstance(d, dict)
        assert d["action"] == "TEST_ACTION"
        assert d["result"] == "SUCCESS"
