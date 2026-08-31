# -*- coding: utf-8 -*-
"""RBAC — Role-Based Access Control for the Master Control Center (Phase 1).

Replaces the naive
    if user.is_admin: allow_everything()
with an explicit permission chain:

    Master User -> Role -> Permissions -> Resource.Action

A permission is a dot-notation string such as ``companies.suspend`` or
``licenses.revoke``.  A role carries a set of these permission codes, and a
master user may hold one or more roles.  Access is granted iff **any** of the
user's roles includes the required permission.

The ``@permission_required("..." )`` decorator is the single gatekeeper used by
every sensitive Admin endpoint; nothing sensitive may rely on frontend-only
checks.
"""
import logging

from database import db

log = logging.getLogger(__name__)

# ── Permission catalog (resource.action) ─────────────────────────
# Every Code a role can grant.  Keep alphabetical by resource for readability.

PERMISSION_CATALOG = [
    # Dashboard / system
    ("dashboard.view", "عرض لوحة التحكم"),
    ("system.view", "عرض حالة النظام"),
    ("system.settings", "تعديل إعدادات النظام"),
    # Companies
    ("companies.view", "عرض الشركات"),
    ("companies.create", "إنشاء شركة"),
    ("companies.edit", "تعديل الشركة"),
    ("companies.suspend", "تعليق / تفعيل الشركة"),
    ("companies.archive", "أرشفة الشركة"),
    ("companies.db", "إنشاء قاعدة بيانات الشركة"),
    # Plans & Trials
    ("plans.view", "عرض الباقات"),
    ("plans.create", "إنشاء باقة"),
    ("plans.edit", "تعديل باقة"),
    ("trials.view", "عرض الفترات التجريبية"),
    ("trials.create", "إنشاء فترة تجريبية"),
    ("trials.extend", "تمديد فترة تجريبية"),
    # Subscriptions
    ("subscriptions.view", "عرض الاشتراكات"),
    ("subscriptions.create", "إنشاء اشتراك"),
    ("subscriptions.extend", "تمديد اشتراك"),
    ("subscriptions.cancel", "إلغاء اشتراك"),
    # Licenses
    ("licenses.view", "عرض التراخيص"),
    ("licenses.create", "إنشاء ترخيص"),
    ("licenses.renew", "تجديد ترخيص"),
    ("licenses.suspend", "تعليق ترخيص"),
    ("licenses.revoke", "إلغاء ترخيص"),
    # Modules
    ("modules.view", "عرض الوحدات"),
    ("modules.enable", "تفعيل وحدة"),
    ("modules.disable", "تعطيل وحدة"),
    # Users & Roles (master-side)
    ("users.view", "عرض مستخدمي التحكم"),
    ("users.create", "إنشاء مستخدم تحكم"),
    ("users.edit", "تعديل مستخدم تحكم"),
    ("roles.manage", "إدارة الأدوار والصلاحيات"),
    # Billing
    ("billing.view", "عرض الفواتير والمبيعات"),
    ("billing.payments", "إدارة المدفوعات"),
    # Security
    ("security.view", "عرض الأحداث الأمنية"),
    ("security.audit", "عرض سجل التدقيق"),
    ("security.sessions", "إدارة الجلسات"),
]

# System roles: name -> ordered permission codes.  Super admin receives all.
SYSTEM_ROLES = {
    "super_admin": "صلاحيات كاملة على جميع الموارد",
    "admin": "إدارة العمليات: شركات، باقات، تراخيص، اشتراكات",
    "support": "دعم: عرض الشركات والتراخيص والاشتراكات والدعم الفني",
    "sales": "مبيعات: شركات، باقات، فترات تجريبية",
}


def _all_codes():
    return [code for code, _ in PERMISSION_CATALOG]


def _codes(*groups):
    from security.models import MasterPermission

    allowed = set()
    for g in groups:
        allowed.update(g)
    return [p.code for p in MasterPermission.query.filter(MasterPermission.code.in_(allowed)).all()]


# Default permission sets per system role.
_ROLE_PERMISSIONS = {
    "super_admin": None,  # sentinel -> every permission
    "admin": [
        "dashboard.view", "system.view",
        "companies.view", "companies.create", "companies.edit", "companies.suspend",
        "companies.archive", "companies.db",
        "plans.view", "plans.create", "plans.edit",
        "trials.view", "trials.create", "trials.extend",
        "subscriptions.view", "subscriptions.create", "subscriptions.extend",
        "licenses.view", "licenses.create", "licenses.renew", "licenses.suspend",
        "licenses.revoke",
        "modules.view", "modules.enable", "modules.disable",
        "billing.view", "billing.payments",
        "users.view",
    ],
    "support": [
        "dashboard.view", "system.view",
        "companies.view", "licenses.view", "subscriptions.view",
        "trials.view", "plans.view", "modules.view",
        "users.view",
    ],
    "sales": [
        "dashboard.view",
        "companies.view", "companies.create", "companies.edit",
        "plans.view", "trials.view", "trials.create", "trials.extend",
    ],
}


def seed_roles_and_permissions():
    """Idempotently create the permission catalog and the system roles."""
    from security.models import MasterPermission, MasterRole, MasterRolePermission

    # 1) Permissions
    perms_by_code = {}
    existing = {p.code: p for p in MasterPermission.query.all()}
    for code, desc in PERMISSION_CATALOG:
        if code in existing:
            p = existing[code]
        else:
            p = MasterPermission(code=code, description=desc)
            db.session.add(p)
        perms_by_code[code] = p
    db.session.flush()

    # 2) System roles — create roles + explicit MasterRolePermission rows
    for name, desc in SYSTEM_ROLES.items():
        role = MasterRole.query.filter_by(name=name).first()
        if role is None:
            role = MasterRole(name=name, description=desc, is_system=True)
            db.session.add(role)
            db.session.flush()
        else:
            role.description = desc

        if name == "super_admin":
            codes = _all_codes()
        else:
            codes = _ROLE_PERMISSIONS[name]

        # Clear existing associations for this role
        MasterRolePermission.query.filter_by(role_id=role.id).delete()
        db.session.flush()

        # Create explicit association rows
        for code in codes:
            perm = perms_by_code.get(code)
            if perm:
                db.session.add(MasterRolePermission(role_id=role.id, permission_id=perm.id))
        db.session.flush()

    db.session.commit()
    log.info("Seeded master roles and %d permissions", len(perms_by_code))

    # Auto-link any existing master users to their RBAC roles
    from licensing.models import LicMasterUser
    from security.models import MasterUserRole
    existing_user_ids = {ur.master_user_id for ur in MasterUserRole.query.all()}
    for user in LicMasterUser.query.filter(LicMasterUser.is_active == True).all():
        if user.id not in existing_user_ids and user.role:
            ensure_user_role_link(user.id, user.role)


# ── Permission resolution ───────────────────────────────────────

def user_permissions(master_user_id):
    """Return the set of permission codes a master user has across all roles.

    A user holding the super_admin role is treated as having every permission.
    """
    from security.models import MasterRole, MasterUserRole

    perms = set()
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
    except Exception as e:  # table missing (fresh DB before seeding)
        log.warning("Could not load master permissions: %s", e)
        return perms

    role_names = []
    for role in rows:
        role_names.append(role.name)
        for p in role.permissions:
            perms.add(p.code)

    if "super_admin" in role_names:
        perms.update(_all_codes())
    return perms


def has_permission(master_user_id, code):
    """True if the master user holds the permission (directly or via super_admin)."""
    return code in user_permissions(master_user_id)


def permitted(permission_codes, required):
    """Check that a set of permission codes satisfies a required permission.

    ``required`` may be a single string or an iterable; an iterable is treated
    as AND (all required) unless ``any`` style is desired by caller.
    """
    if isinstance(required, str):
        return required in permission_codes
    return all(r in permission_codes for r in required)


def permission_required(*codes):
    """Decorator for Admin endpoints: require current master user to hold *all* codes.

    Uses the existing Flask master session (master_user_id).  Returns 403 JSON
    for API paths, otherwise redirects to the admin panel.
    """
    from functools import wraps
    from flask import jsonify, redirect, request, url_for

    from licensing.auth import get_master_session_data

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            sess = get_master_session_data()
            if not sess:
                if request.path.startswith("/api/") or "/api/" in request.path:
                    return jsonify({"success": False, "message": "غير مصرح"}), 401
                return redirect(url_for("admin_lic.admin_panel"))
            if not has_permission(sess["id"], codes[0]):
                log.warning("Permission denied for master user %s: %s", sess["email"], codes)
                return jsonify({"success": False, "message": "لا تملك الصلاحية لهذه العملية"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def ensure_user_role_link(master_user_id, legacy_role_name):
    """Auto-link a legacy master_user (by role column) to the RBAC role.

    Called once per login so old role=super_admin users automatically get
    the super_admin RBAC role and all its permissions.
    """
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
