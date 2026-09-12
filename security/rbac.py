# -*- coding: utf-8 -*-
"""RBAC — explicit role/permission authorization for the control center."""
import logging
import threading
import time as _time

from database import db

log = logging.getLogger(__name__)

# ── RBAC Permissions Cache (in-memory, 60s TTL) ─────────────────
_rbac_cache = {}
_rbac_lock = threading.Lock()
_RbacCacheTTL = 60


def _rbac_cache_get(master_user_id):
    with _rbac_lock:
        entry = _rbac_cache.get(master_user_id)
        if entry and (_time.time() - entry["ts"]) < _RbacCacheTTL:
            return entry["perms"]
    return None


def _rbac_cache_set(master_user_id, perms):
    with _rbac_lock:
        _rbac_cache[master_user_id] = {"perms": perms, "ts": _time.time()}


def invalidate_rbac_cache(master_user_id=None):
    """Invalidate RBAC cache for a user or all users."""
    with _rbac_lock:
        if master_user_id is not None:
            _rbac_cache.pop(master_user_id, None)
        else:
            _rbac_cache.clear()

PERMISSION_CATALOG = [
    ("dashboard.view", "عرض لوحة التحكم"),
    ("system.view", "عرض حالة النظام"),
    ("system.settings", "تعديل إعدادات النظام"),
    ("companies.view", "عرض الشركات"),
    ("companies.create", "إنشاء شركة"),
    ("companies.edit", "تعديل الشركة"),
    ("companies.suspend", "تعليق / تفعيل الشركة"),
    ("companies.archive", "أرشفة الشركة"),
    ("companies.db", "إنشاء قاعدة بيانات الشركة"),
    ("plans.view", "عرض الباقات"),
    ("plans.create", "إنشاء باقة"),
    ("plans.edit", "تعديل باقة"),
    ("trials.view", "عرض الفترات التجريبية"),
    ("trials.create", "إنشاء فترة تجريبية"),
    ("trials.extend", "تمديد فترة تجريبية"),
    ("subscriptions.view", "عرض الاشتراكات"),
    ("subscriptions.create", "إنشاء اشتراك"),
    ("subscriptions.extend", "تمديد اشتراك"),
    ("subscriptions.cancel", "إلغاء اشتراك"),
    ("licenses.view", "عرض التراخيص"),
    ("licenses.create", "إنشاء ترخيص"),
    ("licenses.renew", "تجديد ترخيص"),
    ("licenses.suspend", "تعليق ترخيص"),
    ("licenses.revoke", "إلغاء ترخيص"),
    ("modules.view", "عرض الوحدات"),
    ("modules.enable", "تفعيل وحدة"),
    ("modules.disable", "تعطيل وحدة"),
    ("users.view", "عرض مستخدمي التحكم"),
    ("users.create", "إنشاء مستخدم تحكم"),
    ("users.edit", "تعديل مستخدم تحكم"),
    ("roles.manage", "إدارة الأدوار والصلاحيات"),
    ("billing.view", "عرض الفواتير والمبيعات"),
    ("billing.payments", "إدارة المدفوعات"),
    ("security.view", "عرض الأحداث الأمنية"),
    ("security.audit", "عرض سجل التدقيق"),
    ("security.sessions", "إدارة الجلسات"),
]

SYSTEM_ROLES = {
    "super_admin": "صلاحيات كاملة على جميع الموارد",
    "admin": "إدارة العمليات: شركات، باقات، تراخيص، اشتراكات",
    "support": "دعم: عرض الشركات والتراخيص والاشتراكات والدعم الفني",
    "sales": "مبيعات: شركات، باقات، فترات تجريبية",
}


def _all_codes():
    return [code for code, _ in PERMISSION_CATALOG]


_ROLE_PERMISSIONS = {
    "super_admin": None,
    "admin": [
        "dashboard.view", "system.view",
        "companies.view", "companies.create", "companies.edit", "companies.suspend",
        "companies.archive", "companies.db",
        "plans.view", "plans.create", "plans.edit",
        "trials.view", "trials.create", "trials.extend",
        "subscriptions.view", "subscriptions.create", "subscriptions.extend",
        "licenses.view", "licenses.create", "licenses.renew", "licenses.suspend",
        "licenses.revoke", "modules.view", "modules.enable", "modules.disable",
        "billing.view", "billing.payments", "users.view",
    ],
    "support": [
        "dashboard.view", "system.view", "companies.view", "licenses.view",
        "subscriptions.view", "trials.view", "plans.view", "modules.view", "users.view",
    ],
    "sales": [
        "dashboard.view", "companies.view", "companies.create", "companies.edit",
        "plans.view", "trials.view", "trials.create", "trials.extend",
    ],
}


def seed_roles_and_permissions():
    """Idempotently create the permission catalog, roles, and legacy links."""
    from security.models import MasterPermission, MasterRole, MasterRolePermission

    existing = {p.code: p for p in MasterPermission.query.all()}
    perms_by_code = {}
    for code, desc in PERMISSION_CATALOG:
        permission = existing.get(code)
        if permission is None:
            permission = MasterPermission(code=code, description=desc)
            db.session.add(permission)
        else:
            permission.description = desc
        perms_by_code[code] = permission
    db.session.flush()

    for name, desc in SYSTEM_ROLES.items():
        role = MasterRole.query.filter_by(name=name).first()
        if role is None:
            role = MasterRole(name=name, description=desc, is_system=True)
            db.session.add(role)
            db.session.flush()
        else:
            role.description = desc

        codes = _all_codes() if name == "super_admin" else _ROLE_PERMISSIONS[name]
        MasterRolePermission.query.filter_by(role_id=role.id).delete()
        db.session.flush()
        for code in codes:
            permission = perms_by_code.get(code)
            if permission:
                db.session.add(
                    MasterRolePermission(role_id=role.id, permission_id=permission.id)
                )
        db.session.flush()

    db.session.commit()
    log.info("Seeded master roles and %d permissions", len(perms_by_code))

    from licensing.models import LicMasterUser
    from security.models import MasterUserRole

    existing_user_ids = {ur.master_user_id for ur in MasterUserRole.query.all()}
    for user in LicMasterUser.query.filter(LicMasterUser.is_active == True).all():
        if user.id not in existing_user_ids and user.role:
            ensure_user_role_link(user.id, user.role)


def user_permissions(master_user_id):
    """Return the complete effective permission set for a master user."""
    cached = _rbac_cache_get(master_user_id)
    if cached is not None:
        return cached

    from security.models import MasterRole, MasterUserRole

    try:
        rows = (
            db.session.query(MasterRole)
            .filter(
                MasterRole.id.in_(
                    db.session.query(MasterUserRole.role_id).filter(
                        MasterUserRole.master_user_id == master_user_id
                    )
                )
            )
            .all()
        )
    except Exception as exc:
        log.warning("Could not load master permissions: %s", exc)
        return set()

    permissions = set()
    role_names = set()
    for role in rows:
        role_names.add(role.name)
        permissions.update(p.code for p in role.permissions)
    if "super_admin" in role_names:
        permissions.update(_all_codes())

    _rbac_cache_set(master_user_id, permissions)
    return permissions


def has_permission(master_user_id, code):
    return code in user_permissions(master_user_id)


def permitted(permission_codes, required):
    """Require one permission or every permission in an iterable."""
    if isinstance(required, str):
        return required in permission_codes
    return all(required_code in permission_codes for required_code in required)


def permission_required(*codes):
    """Decorator for sensitive admin endpoints; *all* supplied codes are required."""
    from functools import wraps
    from flask import jsonify, redirect, request, url_for

    from licensing.auth import get_master_session_data

    required_codes = tuple(code for code in codes if code)
    if not required_codes:
        raise ValueError("permission_required requires at least one permission code")

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            session_data = get_master_session_data()
            if not session_data:
                if request.path.startswith("/api/") or "/api/" in request.path:
                    return jsonify({"success": False, "message": "غير مصرح"}), 401
                return redirect(url_for("admin_lic.admin_panel"))

            effective_permissions = user_permissions(session_data["id"])
            if not permitted(effective_permissions, required_codes):
                log.warning(
                    "Permission denied for master user %s: required=%s",
                    session_data.get("email", "unknown"),
                    required_codes,
                )
                return jsonify({"success": False, "message": "لا تملك الصلاحية لهذه العملية"}), 403
            return f(*args, **kwargs)

        return wrapped

    return decorator


def ensure_user_role_link(master_user_id, legacy_role_name):
    """Link legacy role field users to the corresponding RBAC role."""
    from security.models import MasterRole, MasterUserRole

    if not legacy_role_name:
        return
    role = MasterRole.query.filter_by(name=legacy_role_name).first()
    if not role:
        return
    exists = MasterUserRole.query.filter_by(
        master_user_id=master_user_id, role_id=role.id
    ).first()
    if not exists:
        db.session.add(MasterUserRole(master_user_id=master_user_id, role_id=role.id))
        db.session.commit()
        log.info("Auto-linked master user %d to RBAC role %s", master_user_id, legacy_role_name)
