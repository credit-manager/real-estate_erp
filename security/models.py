# -*- coding: utf-8 -*-
"""RBAC + Master security data models (Phase 1).

These tables live in the Master DB and back the ERP Control Center:

    master_roles          – named role (super_admin, admin, support, sales, ...)
    master_permissions    – dot-notation codes: resource.action (companies.view)
    master_role_permissions – many-to-many Role <-> Permission
    master_user_roles     – many-to-many MasterUser <-> Role
    master_sessions       – track authenticated master sessions (revokable)
    master_two_factor     – TOTP secret per master user (2FA)
    master_audit_logs     – "Who/What/When/Company/IP/..." trail for sensitive ops
"""
from datetime import datetime

from database import db


class MasterRole(db.Model):
    __tablename__ = "master_roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False)  # system roles cannot be deleted
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    permissions = db.relationship(
        "MasterPermission",
        secondary="master_role_permissions",
        backref=db.backref("roles", lazy="dynamic"),
        lazy="joined",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_system": self.is_system,
            "permissions": sorted(p.code for p in self.permissions),
        }


class MasterPermission(db.Model):
    __tablename__ = "master_permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(120), unique=True, nullable=False)  # companies.view
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {"id": self.id, "code": self.code, "description": self.description}


class MasterRolePermission(db.Model):
    __tablename__ = "master_role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(
        db.Integer, db.ForeignKey("master_roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id = db.Column(
        db.Integer,
        db.ForeignKey("master_permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class MasterUserRole(db.Model):
    __tablename__ = "master_user_roles"

    id = db.Column(db.Integer, primary_key=True)
    master_user_id = db.Column(
        db.Integer, db.ForeignKey("lic_master_users.id", ondelete="CASCADE"), nullable=False
    )
    role_id = db.Column(
        db.Integer, db.ForeignKey("master_roles.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("master_user_id", "role_id", name="uq_master_user_role"),
    )


class MasterSession(db.Model):
    __tablename__ = "master_sessions"

    id = db.Column(db.Integer, primary_key=True)
    master_user_id = db.Column(
        db.Integer, db.ForeignKey("lic_master_users.id", ondelete="CASCADE"), nullable=False
    )
    jti = db.Column(db.String(64), unique=True, nullable=False)
    refresh_token_hash = db.Column(db.String(128))
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_seen = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "master_user_id": self.master_user_id,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
        }


class MasterTwoFactor(db.Model):
    __tablename__ = "master_two_factor"

    id = db.Column(db.Integer, primary_key=True)
    master_user_id = db.Column(
        db.Integer,
        db.ForeignKey("lic_master_users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    secret = db.Column(db.String(64), nullable=False)
    enabled_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)
    last_used_at = db.Column(db.DateTime)
    recovery_codes_hash = db.Column(db.Text)  # JSON list of hashed recovery codes

    user = db.relationship("LicMasterUser", backref=db.backref("mfa", uselist=False))


class MasterAuditLog(db.Model):
    __tablename__ = "master_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    master_user_id = db.Column(db.Integer)  # Who (null if system action)
    master_user_email = db.Column(db.String(150))
    action = db.Column(db.String(80), nullable=False)  # EXTEND_SUBSCRIPTION etc.
    resource_type = db.Column(db.String(60))
    resource_id = db.Column(db.Integer)
    company_id = db.Column(db.Integer)
    ip = db.Column(db.String(64))
    session_jti = db.Column(db.String(64))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    result = db.Column(db.String(20), default="SUCCESS")  # SUCCESS | FAILED
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "master_user_id": self.master_user_id,
            "master_user_email": self.master_user_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "company_id": self.company_id,
            "ip": self.ip,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ModuleCatalog(db.Model):
    """Master catalog of all ERP modules available in the platform."""
    __tablename__ = "module_catalog"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    version = db.Column(db.String(20), default="1.0.0")
    is_core = db.Column(db.Boolean, default=False)  # core modules can't be disabled
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "name": self.name,
            "name_ar": self.name_ar, "description": self.description,
            "version": self.version, "is_core": self.is_core,
            "is_active": self.is_active, "sort_order": self.sort_order,
        }


class CompanyModule(db.Model):
    """Tracks which modules are enabled for each company."""
    __tablename__ = "company_modules"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)
    module_code = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    feature_flags = db.Column(db.JSON, default=dict)  # per-module feature overrides
    enabled_at = db.Column(db.DateTime, server_default=db.func.now())
    enabled_by = db.Column(db.String(150))
    disabled_at = db.Column(db.DateTime)
    disabled_by = db.Column(db.String(150))

    __table_args__ = (
        db.UniqueConstraint("company_id", "module_code", name="uq_company_module"),
    )

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "module_code": self.module_code, "enabled": self.enabled,
            "feature_flags": self.feature_flags or {},
            "enabled_at": self.enabled_at.isoformat() if self.enabled_at else None,
            "enabled_by": self.enabled_by,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "disabled_by": self.disabled_by,
        }


class SecurityEvent(db.Model):
    """Security events: login attempts, suspicious activity, emergency actions."""
    __tablename__ = "security_events"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    # login_success, login_failure, login_locked, password_changed,
    # session_revoked, emergency_kill_all, account_locked, etc.
    master_user_id = db.Column(db.Integer)
    master_user_email = db.Column(db.String(150))
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    details = db.Column(db.JSON)
    severity = db.Column(db.String(20), default="info")  # info, warning, critical
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "event_type": self.event_type,
            "master_user_id": self.master_user_id,
            "master_user_email": self.master_user_email,
            "ip": self.ip, "user_agent": self.user_agent,
            "details": self.details, "severity": self.severity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
