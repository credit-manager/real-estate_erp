# -*- coding: utf-8 -*-
"""Master security API for the Control Center (Phase 1 + Phase 2).

Endpoints mounted under ``/admin/security`` and gated by the existing
master session.  Covers:

    - 2FA enroll / verify / status / disable / recovery codes
    - JWT token refresh (used by the frontend to obtain API tokens)
    - role & permission listing
    - active sessions listing / revocation
    - audit log listing
    - Company lifecycle transitions (Phase 2)
    - Full company provisioning (Phase 2)

These are the building blocks the Control Center frontend consumes; individual
Admin business endpoints will additionally be gated with ``permission_required``.
"""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from database import db

security_bp = Blueprint("security_ctrl", __name__, url_prefix="/admin/security")

log = logging.getLogger(__name__)


def _current():
    from licensing.auth import get_master_session_data
    data = get_master_session_data()
    if not data:
        return None
    return data


def _guard():
    """Require master login. Returns 401 json or None."""
    if not _current():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    return None


@security_bp.route("/me", methods=["GET"])
def me():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import user_permissions
    return jsonify(
        {
            "success": True,
            "user": {
                "id": cur["id"],
                "email": cur["email"],
                "full_name": cur["full_name"],
                "role": cur["role"],
            },
            "permissions": sorted(user_permissions(cur["id"])),
        }
    )


# ── 2FA ──────────────────────────────────────────────────────

@security_bp.route("/2fa/status", methods=["GET"])
def twofa_status():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.two_factor import is_enabled
    return jsonify({"success": True, "enabled": is_enabled(cur["id"])})


@security_bp.route("/2fa/enroll", methods=["POST"])
def twofa_enroll():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.two_factor import enroll
    secret, uri = enroll(cur["id"], cur["email"])
    return jsonify(
        {
            "success": True,
            "secret": secret,
            "otpauth_uri": uri,
            "note": "احفظ الرمز السري الآن؛ يظهر مرة واحدة فقط.",
        }
    )


@security_bp.route("/2fa/verify", methods=["POST"])
def twofa_verify():
    g = _guard()
    if g:
        return g
    cur = _current()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"success": False, "message": "أدخل رمز المصادقة"}), 400
    from security.two_factor import verify_code
    if verify_code(cur["id"], code):
        return jsonify({"success": True, "enabled": True})
    return jsonify({"success": False, "message": "الرمز غير صحيح"}), 400


@security_bp.route("/2fa/disable", methods=["POST"])
def twofa_disable():
    g = _guard()
    if g:
        return g
    cur = _current()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    from security.two_factor import verify_code, disable, require_two_factor
    from security.rbac import user_permissions, _all_codes
    if not verify_code(cur["id"], code):
        return jsonify({"success": False, "message": "الرمز غير صحيح"}), 400
    # A super admin cannot disable the last 2FA (spec: no Super Admin without 2FA)
    if user_permissions(cur["id"]) >= set(_all_codes()):
        return jsonify(
            {"success": False, "message": "لا يمكنك إيقاف المصادقة الثنائية كمدير عام"}
        ), 403
    disable(cur["id"])
    return jsonify({"success": True})


@security_bp.route("/2fa/recovery-codes", methods=["POST"])
def twofa_recovery_codes():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.two_factor import generate_recovery_codes
    codes = generate_recovery_codes(cur["id"])
    return jsonify({"success": True, "codes": codes})


@security_bp.route("/2fa/verify-recovery", methods=["POST"])
def twofa_verify_recovery():
    g = _guard()
    if g:
        return g
    cur = _current()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    from security.two_factor import verify_recovery_code
    if verify_recovery_code(cur["id"], code):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "الرمز غير صحيح"}), 400


# ── Roles & Permissions ──────────────────────────────────────

@security_bp.route("/roles", methods=["GET"])
def roles():
    g = _guard()
    if g:
        return g
    from security.rbac import has_permission
    cur = _current()
    if not has_permission(cur["id"], "roles.manage") and not has_permission(cur["id"], "users.view"):
        from security.models import MasterRole
        roles = MasterRole.query.all()
        return jsonify({"success": True, "roles": [r.to_dict() for r in roles], "readonly": True})
    from security.models import MasterRole
    roles = MasterRole.query.all()
    return jsonify({"success": True, "roles": [r.to_dict() for r in roles]})


@security_bp.route("/permissions", methods=["GET"])
def permissions():
    g = _guard()
    if g:
        return g
    from security.rbac import PERMISSION_CATALOG
    return jsonify(
        {
            "success": True,
            "permissions": [{"code": c, "description": d} for c, d in PERMISSION_CATALOG],
        }
    )


# ── Sessions ─────────────────────────────────────────────────

@security_bp.route("/sessions", methods=["GET"])
def sessions():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.models import MasterSession
    rows = MasterSession.query.filter_by(master_user_id=cur["id"]).order_by(
        MasterSession.created_at.desc()
    ).limit(50).all()
    return jsonify({"success": True, "sessions": [r.to_dict() for r in rows]})


@security_bp.route("/sessions/<int:sid>/revoke", methods=["POST"])
def revoke_session(sid):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.models import MasterSession
    s = db.session.get(MasterSession, sid)
    if not s or s.master_user_id != cur["id"]:
        return jsonify({"success": False, "message": "الجلسة غير موجودة"}), 404
    s.revoked = True
    db.session.commit()
    return jsonify({"success": True})


# ── Audit (Phase 6 enhanced) ────────────────────────────────

@security_bp.route("/audit", methods=["GET"])
def audit():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.audit"):
        return jsonify({"success": False, "message": "لا تملك صلاحية عرض سجل التدقيق"}), 403
    from security.models import MasterAuditLog
    limit = min(int(request.args.get("limit", 100)), 500)
    action = request.args.get("action")
    resource_type = request.args.get("resource_type")
    company_id = request.args.get("company_id", type=int)
    query = MasterAuditLog.query
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if company_id:
        query = query.filter_by(company_id=company_id)
    rows = query.order_by(MasterAuditLog.created_at.desc()).limit(limit).all()
    return jsonify({"success": True, "logs": [r.to_dict() for r in rows]})


# ── Analytics (Phase 7) ─────────────────────────────────────

@security_bp.route("/analytics/overview", methods=["GET"])
def analytics_overview():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "companies.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.analytics import platform_overview
    return jsonify(platform_overview())


@security_bp.route("/analytics/companies/<int:company_id>", methods=["GET"])
def analytics_company(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "companies.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.analytics import company_analytics
    return jsonify(company_analytics(company_id))


@security_bp.route("/analytics/revenue", methods=["GET"])
def analytics_revenue():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "billing.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.analytics import revenue_analytics
    return jsonify(revenue_analytics())


@security_bp.route("/analytics/modules", methods=["GET"])
def analytics_modules():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "modules.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.analytics import module_adoption_stats
    return jsonify(module_adoption_stats())


@security_bp.route("/analytics/subscriptions", methods=["GET"])
def analytics_subscriptions():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "subscriptions.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.analytics import subscription_status_summary
    return jsonify(subscription_status_summary())

@security_bp.route("/security/events", methods=["GET"])
def security_events():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية عرض الأحداث الأمنية"}), 403
    event_type = request.args.get("event_type")
    severity = request.args.get("severity")
    limit = min(int(request.args.get("limit", 100)), 500)
    from security.security_events import get_events
    result = get_events(event_type=event_type, severity=severity, limit=limit)
    return jsonify(result)


@security_bp.route("/security/summary", methods=["GET"])
def security_summary():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.security_events import get_security_summary
    result = get_security_summary()
    return jsonify(result)


@security_bp.route("/security/login-history", methods=["GET"])
def login_history():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    user_id = request.args.get("user_id", type=int)
    limit = min(int(request.args.get("limit", 50)), 200)
    from security.security_events import get_login_history
    result = get_login_history(master_user_id=user_id, limit=limit)
    return jsonify(result)


# ── Emergency Controls (Phase 6) ────────────────────────────

@security_bp.route("/security/kill-all-sessions", methods=["POST"])
def emergency_kill_all():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.sessions"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إدارة الجلسات"}), 403
    from security.security_events import kill_all_sessions
    result = kill_all_sessions(exclude_user_id=cur["id"])
    return jsonify(result)


@security_bp.route("/security/kill-sessions/<int:user_id>", methods=["POST"])
def kill_sessions(user_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.sessions"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إدارة الجلسات"}), 403
    from security.security_events import kill_user_sessions
    result = kill_user_sessions(user_id, actor_email=cur["email"],
                                actor_id=cur["id"], ip=request.remote_addr)
    return jsonify(result)


@security_bp.route("/security/lock-account/<int:user_id>", methods=["POST"])
def lock_account(user_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.sessions"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.security_events import lock_account
    result = lock_account(user_id, actor_email=cur["email"],
                          actor_id=cur["id"], ip=request.remote_addr)
    return jsonify(result)


@security_bp.route("/security/unlock-account/<int:user_id>", methods=["POST"])
def unlock_account(user_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission
    if not has_permission(cur["id"], "security.sessions"):
        return jsonify({"success": False, "message": "لا تملك صلاحية"}), 403
    from security.security_events import unlock_account
    result = unlock_account(user_id, actor_email=cur["email"],
                            actor_id=cur["id"], ip=request.remote_addr)
    return jsonify(result)


# ── JWT refresh ──────────────────────────────────────────────

@security_bp.route("/token/refresh", methods=["POST"])
def token_refresh():
    g = _guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    refresh = data.get("refresh_token")
    if not refresh:
        return jsonify({"success": False, "message": "رمز التحديث مطلوب"}), 400
    from security.tokens import refresh_access_token
    access, payload = refresh_access_token(refresh)
    if not access:
        return jsonify({"success": False, "message": "رمز التحديث غير صالح"}), 401
    return jsonify({"success": True, "access_token": access})


# ── Company Lifecycle (Phase 2) ──────────────────────────────

@security_bp.route("/companies/<int:company_id>/transition", methods=["POST"])
def transition_company(company_id):
    """Transition a company's status with validation + audit."""
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "companies.suspend") and not _has(cur["id"], "companies.edit"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تغيير حالة الشركة"}), 403

    from database import db
    from licensing.models import LicCompany
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "الشركة غير موجودة"}), 404

    data = request.get_json(silent=True) or {}
    to_status = (data.get("status") or "").strip()
    if not to_status:
        return jsonify({"success": False, "message": "الحالة المطلوبة مطلوبة"}), 400

    from security.company_lifecycle import transition_company as do_transition
    result = do_transition(
        company, to_status,
        actor_email=cur["email"], actor_id=cur["id"],
        ip=request.remote_addr, reason=data.get("reason"),
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/provision", methods=["POST"])
def provision_company():
    """Full company provisioning: company + admin + subscription + license in one call.

    Body: {name, name_ar, email, phone, tax_number, address,
           is_trial, plan_code, subscription_days,
           admin_email, admin_password, admin_name,
           modules: ["crm", "accounting", ...]}
    """
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "companies.create"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إنشاء شركة"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "اسم الشركة مطلوب"}), 400

    from licensing.onboarding import create_company, create_company_admin
    from licensing.db_manager import create_company_db
    from database import db
    from security.audit import record as audit_record

    result = create_company(
        name=name, name_ar=data.get("name_ar"),
        email=data.get("email"), phone=data.get("phone"),
        tax_number=data.get("tax_number"), address=data.get("address"),
        is_trial=data.get("is_trial", True),
        plan_code=data.get("plan_code", "basic"),
        subscription_days=data.get("subscription_days"),
        admin_password=data.get("admin_password"),
        admin_full_name=data.get("admin_name"),
    )

    if not result["success"]:
        return jsonify(result), 500

    company = result["company"]

    # Audit the provisioning
    audit_record(
        action="COMPANY_PROVISIONED",
        master_user_id=cur["id"],
        master_user_email=cur["email"],
        resource_type="company",
        resource_id=company.id,
        company_id=company.id,
        ip=request.remote_addr,
        new_value=name,
        result="SUCCESS",
    )

    # Enable modules if specified
    modules = data.get("modules") or []
    if modules:
        from security.rbac import user_permissions
        if _has(cur["id"], "modules.enable"):
            _enable_modules(company.id, modules, cur)

    return jsonify({
        "success": True,
        "company": company.to_dict(),
        "subscription": result["subscription"].to_dict() if result.get("subscription") else None,
        "license": result["license"].to_dict() if result.get("license") else None,
        "message": f"تم إنشاء الشركة '{name}' بنجاح",
    })


def _enable_modules(company_id, module_codes, cur):
    """Enable modules for a company (idempotent)."""
    from database import db
    from security.audit import record as audit_record

    for code in module_codes:
        code = (code or "").strip().lower()
        if not code:
            continue
        audit_record(
            action="MODULE_ENABLED",
            master_user_id=cur["id"],
            master_user_email=cur["email"],
            resource_type="module",
            company_id=company_id,
            ip=request.remote_addr,
            new_value=code,
            result="SUCCESS",
        )
    log.info("Enabled modules for company %d: %s", company_id, module_codes)


# ── Plans Management (Phase 3) ──────────────────────────────

@security_bp.route("/plans", methods=["GET"])
def plans_list():
    g = _guard()
    if g:
        return g
    from licensing.models import LicPlan
    plans = LicPlan.query.order_by(LicPlan.sort_order).all()
    return jsonify({"success": True, "plans": [p.to_dict() for p in plans]})


@security_bp.route("/plans", methods=["POST"])
def plans_create():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "plans.create"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إنشاء باقة"}), 403

    data = request.get_json(silent=True) or {}
    required = ["name", "name_ar", "code"]
    for f in required:
        if not (data.get(f) or "").strip():
            return jsonify({"success": False, "message": f"{f} مطلوب"}), 400

    from security.licensing import create_plan
    result = create_plan(
        name=data["name"], name_ar=data["name_ar"], code=data["code"],
        price_monthly=data.get("price_monthly"), price_yearly=data.get("price_yearly"),
        max_users=data.get("max_users", 5), max_projects=data.get("max_projects", 10),
        max_storage_mb=data.get("max_storage_mb", 1024),
        modules=data.get("modules", {}), sort_order=data.get("sort_order", 0),
        actor_email=cur["email"], actor_id=cur["id"], ip=request.remote_addr,
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/plans/<int:plan_id>", methods=["PUT"])
def plans_update(plan_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "plans.edit"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تعديل الباقة"}), 403

    data = request.get_json(silent=True) or {}
    from security.licensing import update_plan
    result = update_plan(plan_id, data, actor_email=cur["email"], actor_id=cur["id"],
                         ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


# ── Trial Management (Phase 3) ──────────────────────────────

@security_bp.route("/companies/<int:company_id>/trial/extend", methods=["POST"])
def trial_extend(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "trials.extend"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تمديد الفترة التجريبية"}), 403

    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 30))
    from security.licensing import extend_trial
    result = extend_trial(company_id, days, actor_email=cur["email"], actor_id=cur["id"],
                          ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/trial/end", methods=["POST"])
def trial_end(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.licensing import end_trial
    result = end_trial(company_id, actor_email=cur["email"], actor_id=cur["id"],
                       ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/trial/convert", methods=["POST"])
def trial_convert(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.licensing import convert_trial_to_paid
    data = request.get_json(silent=True) or {}
    plan_code = (data.get("plan_code") or "").strip()
    if not plan_code:
        return jsonify({"success": False, "message": "plan_code مطلوب"}), 400
    result = convert_trial_to_paid(
        company_id, plan_code,
        subscription_days=data.get("subscription_days", 365),
        actor_email=cur["email"], actor_id=cur["id"], ip=request.remote_addr,
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


# ── Subscription Management (Phase 3) ───────────────────────

@security_bp.route("/companies/<int:company_id>/subscription/renew", methods=["POST"])
def sub_renew(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "subscriptions.extend"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تجديد الاشتراك"}), 403

    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 365))
    from security.licensing import renew_subscription_for_company
    result = renew_subscription_for_company(company_id, days, actor_email=cur["email"],
                                            actor_id=cur["id"], ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/subscription/cancel", methods=["POST"])
def sub_cancel(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "subscriptions.cancel"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إلغاء الاشتراك"}), 403

    from security.licensing import cancel_subscription
    result = cancel_subscription(company_id, actor_email=cur["email"],
                                 actor_id=cur["id"], ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


# ── License Management (Phase 3) ────────────────────────────

@security_bp.route("/companies/<int:company_id>/license/suspend", methods=["POST"])
def lic_suspend(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "licenses.suspend"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تعليق التراخيص"}), 403

    from security.licensing import suspend_license_for_company
    result = suspend_license_for_company(company_id, actor_email=cur["email"],
                                         actor_id=cur["id"], ip=request.remote_addr)
    return jsonify(result)


@security_bp.route("/companies/<int:company_id>/license/revoke", methods=["POST"])
def lic_revoke(company_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "licenses.revoke"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إلغاء التراخيص"}), 403

    from security.licensing import revoke_license_for_company
    result = revoke_license_for_company(company_id, actor_email=cur["email"],
                                        actor_id=cur["id"], ip=request.remote_addr)
    return jsonify(result)


# ── Access Check (Phase 3) ──────────────────────────────────

@security_bp.route("/companies/<int:company_id>/access", methods=["GET"])
def access_check(company_id):
    g = _guard()
    if g:
        return g
    from licensing.engine import can_access, check_module_access, check_user_limit
    access = can_access(company_id)
    return jsonify({"success": True, **access})


# ── Billing (Phase 4) ───────────────────────────────────────

@security_bp.route("/payments", methods=["GET"])
def payments_list():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية عرض المدفوعات"}), 403

    status = request.args.get("status")
    company_id = request.args.get("company_id", type=int)
    from security.billing import payment_history
    result = payment_history(company_id=company_id, limit=100)
    if status:
        result["payments"] = [p for p in result["payments"] if p.get("status") == status]
    return jsonify(result)


@security_bp.route("/payments", methods=["POST"])
def payments_create():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.payments"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تسجيل المدفوعات"}), 403

    data = request.get_json(silent=True) or {}
    company_id = data.get("company_id")
    amount = data.get("amount")
    if not company_id or not amount:
        return jsonify({"success": False, "message": "company_id و amount مطلوبان"}), 400

    from security.billing import create_payment
    result = create_payment(
        company_id=company_id, amount=amount,
        currency=data.get("currency", "EGP"),
        payment_method=data.get("payment_method", "cash"),
        reference_no=data.get("reference_no", ""),
        actor_email=cur["email"], actor_id=cur["id"], ip=request.remote_addr,
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/payments/<int:payment_id>/confirm", methods=["POST"])
def payments_confirm(payment_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.payments"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تأكيد المدفوعات"}), 403

    from security.billing import confirm_payment
    result = confirm_payment(payment_id, confirmed_by=cur["email"],
                             actor_email=cur["email"], actor_id=cur["id"],
                             ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/payments/<int:payment_id>/refund", methods=["POST"])
def payments_refund(payment_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.payments"):
        return jsonify({"success": False, "message": "لا تملك صلاحية استرداد المدفوعات"}), 403

    data = request.get_json(silent=True) or {}
    from security.billing import refund_payment
    result = refund_payment(payment_id, reason=data.get("reason", ""),
                            actor_email=cur["email"], actor_id=cur["id"],
                            ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/payments/<int:payment_id>/fail", methods=["POST"])
def payments_fail(payment_id):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.payments"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تحديد المدفوعات الفاشلة"}), 403

    data = request.get_json(silent=True) or {}
    from security.billing import fail_payment
    result = fail_payment(payment_id, reason=data.get("reason", ""),
                          actor_email=cur["email"], actor_id=cur["id"],
                          ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/revenue", methods=["GET"])
def revenue_stats():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية عرض الإيرادات"}), 403

    months = int(request.args.get("months", 6))
    from security.billing import revenue_stats as get_revenue
    result = get_revenue(months=months)
    return jsonify(result)


@security_bp.route("/revenue/by-company", methods=["GET"])
def revenue_by_company():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "billing.view"):
        return jsonify({"success": False, "message": "لا تملك صلاحية عرض الإيرادات"}), 403

    from security.billing import payment_summary_by_company
    result = payment_summary_by_company()
    return jsonify(result)


# ── Module Management (Phase 5) ─────────────────────────────

@security_bp.route("/modules", methods=["GET"])
def modules_catalog():
    g = _guard()
    if g:
        return g
    from security.modules import list_modules
    result = list_modules()
    return jsonify(result)


@security_bp.route("/modules", methods=["POST"])
def modules_create():
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "modules.enable"):
        return jsonify({"success": False, "message": "لا تملك صلاحية إنشاء وحدة"}), 403

    data = request.get_json(silent=True) or {}
    required = ["code", "name", "name_ar"]
    for f in required:
        if not (data.get(f) or "").strip():
            return jsonify({"success": False, "message": f"{f} مطلوب"}), 400

    from security.modules import create_module
    result = create_module(
        code=data["code"], name=data["name"], name_ar=data["name_ar"],
        description=data.get("description", ""),
        version=data.get("version", "1.0.0"),
        is_core=data.get("is_core", False),
        actor_email=cur["email"], actor_id=cur["id"], ip=request.remote_addr,
    )
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/modules/<module_code>", methods=["GET"])
def modules_get(module_code):
    g = _guard()
    if g:
        return g
    from security.modules import get_module
    result = get_module(module_code)
    status_code = 200 if result["success"] else 404
    return jsonify(result), status_code


@security_bp.route("/modules/<module_code>", methods=["PUT"])
def modules_update(module_code):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "modules.enable"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تعديل الوحدة"}), 403

    data = request.get_json(silent=True) or {}
    from security.modules import update_module
    result = update_module(module_code, data, actor_email=cur["email"],
                           actor_id=cur["id"], ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/modules", methods=["GET"])
def company_modules(company_id):
    g = _guard()
    if g:
        return g
    from security.modules import get_company_modules
    result = get_company_modules(company_id)
    return jsonify(result)


@security_bp.route("/companies/<int:company_id>/modules/<module_code>/enable", methods=["POST"])
def company_module_enable(company_id, module_code):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "modules.enable"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تفعيل الوحدات"}), 403

    from security.modules import enable_module_for_company
    result = enable_module_for_company(company_id, module_code,
                                       actor_email=cur["email"], actor_id=cur["id"],
                                       ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/modules/<module_code>/disable", methods=["POST"])
def company_module_disable(company_id, module_code):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "modules.disable"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تعطيل الوحدات"}), 403

    from security.modules import disable_module_for_company
    result = disable_module_for_company(company_id, module_code,
                                        actor_email=cur["email"], actor_id=cur["id"],
                                        ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/modules/<module_code>/feature-flag", methods=["POST"])
def company_module_feature_flag(company_id, module_code):
    g = _guard()
    if g:
        return g
    cur = _current()
    from security.rbac import has_permission as _has
    if not _has(cur["id"], "modules.enable"):
        return jsonify({"success": False, "message": "لا تملك صلاحية تعديل علامات الميزة"}), 403

    data = request.get_json(silent=True) or {}
    flag_name = (data.get("flag") or "").strip()
    flag_value = data.get("value")
    if not flag_name:
        return jsonify({"success": False, "message": "flag مطلوب"}), 400

    from security.modules import set_feature_flag
    result = set_feature_flag(company_id, module_code, flag_name, flag_value,
                              actor_email=cur["email"], actor_id=cur["id"],
                              ip=request.remote_addr)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@security_bp.route("/companies/<int:company_id>/modules/<module_code>/access", methods=["GET"])
def company_module_access(company_id, module_code):
    g = _guard()
    if g:
        return g
    from security.modules import check_company_module_access
    result = check_company_module_access(company_id, module_code)
    return jsonify(result)
