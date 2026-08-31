# -*- coding: utf-8 -*-
"""Admin API routes for licensing & company management."""
import logging
from datetime import date, timedelta
from flask import Blueprint, request, jsonify, session, render_template
from sqlalchemy import text

from database import db
from licensing.models import LicCompany, LicSubscription, LicLicense, LicPayment, LicPlan, LicDatabaseRegistry, LicMasterUser, LicActivityLog, LicCompanyUser
from licensing.engine import can_access, renew_subscription, suspend_license, revoke_license
from licensing.onboarding import create_company, upgrade_plan, suspend_company, reactivate_company
from licensing.plans_data import GRACE_PERIOD_DAYS

log = logging.getLogger(__name__)

admin_lic_bp = Blueprint("admin_lic", __name__, url_prefix="/admin")


# ── Admin Panel Page ──────────────────────────────────────────

@admin_lic_bp.route("/")
def admin_panel():
    return render_template("admin_panel.html")


# ── Master Login / Logout ───────────────────────────────────

@admin_lic_bp.route("/login", methods=["POST"])
def master_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    from licensing.auth import authenticate_master_user
    from licensing.auth import _check_lock as _lic_check_lock
    from licensing.auth import _register_failure as _lic_register_failure

    lock_key = f"{request.remote_addr}:{email}"
    if _lic_check_lock(lock_key):
        return jsonify({
            "success": False, "message": "تم قفل محاولات الدخول مؤقتاً.",
        }), 429

    result = authenticate_master_user(email, password)
    if not result["success"]:
        _lic_register_failure(lock_key)
        return jsonify(result), 401

    usr = LicMasterUser.query.filter_by(email=email).first()
    if usr:
        _log_activity(usr, "login")
    return jsonify(result)


@admin_lic_bp.route("/logout", methods=["POST"])
def master_logout():
    from licensing.auth import logout_master_user
    user = _require_admin()
    if user:
        _log_activity(user, "logout")
    logout_master_user()
    return jsonify({"success": True})


def _require_admin():
    from licensing.auth import is_master_logged_in
    if not is_master_logged_in():
        return None
    uid = session.get("master_user_id")
    user = db.session.get(LicMasterUser, uid)
    if not user or not user.is_active:
        return None
    return user


def _admin_or_abort():
    user = _require_admin()
    if not user:
        return None, (jsonify({"success": False, "message": "Unauthorized"}), 401)
    return user, None


def _log_activity(user, action, target_type=None, target_id=None, details=None):
    try:
        log = LicActivityLog(
            actor_id=user.id, actor_email=user.email, action=action,
            target_type=target_type, target_id=target_id, details=details,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── Dashboard ───────────────────────────────────────────────

@admin_lic_bp.route("/dashboard")
def dashboard():
    user, err = _admin_or_abort()
    if err:
        return err

    total = LicCompany.query.filter(LicCompany.status != "deleted").count()
    active = LicCompany.query.filter_by(status="active").count()
    suspended = LicCompany.query.filter_by(status="suspended").count()
    archived = LicCompany.query.filter_by(status="deleted").count()
    trials = LicSubscription.query.filter_by(status="trial").count()

    today = date.today()
    in7 = today + timedelta(days=7)
    grace_end = today + timedelta(days=GRACE_PERIOD_DAYS)

    sub_statuses = ["active", "trial"]

    expiring_7d = LicSubscription.query.filter(
        LicSubscription.status.in_(sub_statuses),
        LicSubscription.end_date >= today,
        LicSubscription.end_date <= in7,
    ).count()

    expiring_soon = LicSubscription.query.filter(
        LicSubscription.status.in_(sub_statuses),
        LicSubscription.end_date <= grace_end,
        LicSubscription.end_date >= today,
    ).count()

    grace_count = LicSubscription.query.filter(
        LicSubscription.status.in_(sub_statuses),
        LicSubscription.end_date < today,
        LicSubscription.end_date + timedelta(days=GRACE_PERIOD_DAYS) >= today,
    ).count()

    expired = LicSubscription.query.filter(
        LicSubscription.status.in_(sub_statuses),
        LicSubscription.end_date < today,
    ).count()

    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(LicPayment.amount), 0)
    ).filter_by(status="confirmed").scalar()

    total_users = LicCompanyUser.query.count()
    active_users = LicCompanyUser.query.filter_by(is_active=True).count()

    ready_db_ids = {
        r.company_id for r in LicDatabaseRegistry.query.filter_by(status="active").all()
    }
    total_databases = len(ready_db_ids)
    failed_databases = active - total_databases
    pending_databases = LicDatabaseRegistry.query.filter(
        LicDatabaseRegistry.status.in_(["provisioning", "migrating"])
    ).count()
    archived_databases = LicDatabaseRegistry.query.filter_by(status="archived").count()

    revoked_licenses = LicLicense.query.filter_by(status="revoked").count()
    suspended_licenses = LicLicense.query.filter_by(status="suspended").count()
    pending_payments = LicPayment.query.filter(LicPayment.status != "confirmed").count()

    # "Needs attention" alerts
    alerts = []
    if expiring_7d:
        alerts.append({
            "type": "expiring_7d", "severity": "warn",
            "count": expiring_7d,
            "title": "اشتراكات تنتهي خلال 7 أيام",
        })
    if failed_databases > 0:
        alerts.append({
            "type": "failed_databases", "severity": "err",
            "count": failed_databases,
            "title": "قواعد بيانات فشل إنشاؤها",
        })
    if grace_count:
        alerts.append({
            "type": "grace_period", "severity": "warn",
            "count": grace_count,
            "title": "شركات في فترة السماح",
        })
    if pending_payments:
        alerts.append({
            "type": "pending_payments", "severity": "info",
            "count": pending_payments,
            "title": "مدفوعات معلقة لم تُؤكد",
        })
    if pending_databases:
        alerts.append({
            "type": "pending_databases", "severity": "info",
            "count": pending_databases,
            "title": "قواعد بيانات قيد الإنشاء",
        })

    # Latest companies
    latest = []
    for c in LicCompany.query.filter(LicCompany.status != "deleted") \
            .order_by(LicCompany.id.desc()).limit(6).all():
        d = c.to_dict()
        sub = c.active_subscription
        if sub:
            d["users_limit"] = sub.plan.max_users if sub.plan else None
            d["plan_name"] = (sub.plan.name if sub.plan else None) or (sub.plan.code if sub.plan else None) or sub.plan_code
        d["database_ready"] = c.id in ready_db_ids
        latest.append(d)

    return jsonify({
        "success": True,
        "stats": {
            "total_companies": total,
            "active": active,
            "suspended": suspended,
            "archived": archived,
            "trials": trials,
            "expired": expired,
            "expiring_soon": expiring_soon,
            "expiring_7d": expiring_7d,
            "grace_count": grace_count,
            "total_revenue": float(total_revenue),
            "total_users": total_users,
            "active_users": active_users,
            "total_databases": total_databases,
            "failed_databases": failed_databases,
            "pending_databases": pending_databases,
            "archived_databases": archived_databases,
            "total_licenses": LicLicense.query.count(),
            "active_licenses": LicLicense.query.filter_by(status="active").count(),
            "suspended_licenses": suspended_licenses,
            "revoked_licenses": revoked_licenses,
            "total_payments": LicPayment.query.count(),
            "pending_payments": pending_payments,
        },
        "alerts": alerts,
        "latest_companies": latest,
    })


# ── Companies ───────────────────────────────────────────────

def _company_users_count(company):
    """Count active users in the company's own DB, falling back to the master bridge."""
    try:
        from licensing.db_manager import get_company_engine
        engine = get_company_engine(company)
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true")).scalar()
            if n is not None:
                return int(n)
    except Exception:
        pass
    return LicCompanyUser.query.filter_by(company_id=company.id, is_active=True).count()


@admin_lic_bp.route("/companies", methods=["GET"])
def list_companies():
    user, err = _admin_or_abort()
    if err:
        return err

    status = request.args.get("status")
    query = LicCompany.query
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(LicCompany.status != "deleted")
    companies = query.order_by(LicCompany.id.desc()).all()

    result = []
    for c in companies:
        d = c.to_dict()
        sub = c.active_subscription
        d["users_used"] = _company_users_count(c)
        d["database_ready"] = False
        if sub:
            plan = sub.plan
            d["users_limit"] = plan.max_users if plan else None
            d["max_projects"] = plan.max_projects if plan else None
            d["plan_name"] = (plan.name if plan else None) or sub.plan_code
            d["plan_modules"] = (plan.modules or {}) if plan else {}
        if LicDatabaseRegistry.query.filter_by(company_id=c.id, status="active").first():
            d["database_ready"] = True
        result.append(d)

    return jsonify({"success": True, "companies": result})


@admin_lic_bp.route("/companies", methods=["POST"])
def create_new_company():
    user, err = _admin_or_abort()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Company name is required"}), 400

    result = create_company(
        name=name, name_ar=data.get("name_ar"), email=data.get("email"),
        phone=data.get("phone"), tax_number=data.get("tax_number"),
        address=data.get("address"),
        is_trial=data.get("is_trial", True), plan_code=data.get("plan_code", "basic"),
        subscription_days=data.get("subscription_days"),
    )

    if not result["success"]:
        company_obj = result.get("company")
        if company_obj and hasattr(company_obj, "to_dict"):
            result["company"] = company_obj.to_dict()
        return jsonify(result), 500

    company = result["company"]
    _log_activity(user, "company_created", "company", company.id, {"name": name})
    new_license = result.get("license")
    if new_license:
        _log_activity(user, "license_created", target_type="license", target_id=new_license.id,
                      details={"license_key": new_license.license_key})
    admin_email = data.get("admin_email")
    admin_password = data.get("admin_password")
    if admin_email and admin_password:
        from licensing.onboarding import create_company_admin
        create_company_admin(company.id, admin_email, admin_password, full_name=data.get("admin_name"))

    return jsonify({
        "success": True,
        "company": company.to_dict(),
        "subscription": result["subscription"].to_dict() if result.get("subscription") else None,
        "license": result["license"].to_dict() if result.get("license") else None,
        "message": result["message"],
    })


@admin_lic_bp.route("/companies/<int:company_id>")
def get_company(company_id):
    user, err = _admin_or_abort()
    if err:
        return err

    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    d = company.to_dict()

    sub = company.active_subscription
    if sub:
        plan = db.session.get(LicPlan, sub.plan_id)
        d["subscription"] = sub.to_dict()
        d["subscription"]["plan"] = plan.to_dict() if plan else None
        d["users_limit"] = plan.max_users if plan else None
        d["max_projects"] = plan.max_projects if plan else None

    lic = company.active_license
    if lic:
        d["license"] = lic.to_dict()

    d["access"] = can_access(company_id)
    d["users_count"] = _company_users_count(company)

    db_reg = LicDatabaseRegistry.query.filter_by(company_id=company_id, status="active").first()
    d["database"] = db_reg.to_dict() if db_reg else None

    return jsonify({"success": True, "company": d})


# ── Company Actions ─────────────────────────────────────────

@admin_lic_bp.route("/companies/<int:company_id>/renew", methods=["POST"])
def renew_company(company_id):
    user, err = _admin_or_abort()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    days = data.get("days", 365)

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active", "grace", "expired"]),
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return jsonify({"success": False, "message": "No subscription found"}), 404

    renewed = renew_subscription(sub.id, days)
    if not renewed:
        return jsonify({"success": False, "message": "Renewal failed"}), 500

    return jsonify({"success": True, "subscription": renewed.to_dict(), "message": f"Renewed for {days} days"})


@admin_lic_bp.route("/companies/<int:company_id>/upgrade", methods=["POST"])
def upgrade_company(company_id):
    user, err = _admin_or_abort()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    plan_code = (data.get("plan_code") or "").strip()
    if not plan_code:
        return jsonify({"success": False, "message": "plan_code is required"}), 400

    result = upgrade_plan(company_id, plan_code)
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)


def _log_license_events(user, action, licenses):
    for lic in licenses:
        _log_activity(user, action, target_type="license", target_id=lic.id,
                      details={"license_key": lic.license_key})


@admin_lic_bp.route("/companies/<int:company_id>/suspend", methods=["POST"])
def suspend_company_action(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    affected = LicLicense.query.filter(LicLicense.company_id == company_id, LicLicense.status == "active").all()
    result = suspend_company(company_id)
    suspend_license(company_id)
    _log_activity(user, "company_suspended", "company", company_id)
    _log_license_events(user, "license_suspended", affected)
    return jsonify(result)


@admin_lic_bp.route("/companies/<int:company_id>/reactivate", methods=["POST"])
def reactivate_company_action(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    from datetime import date as _date
    result = reactivate_company(company_id)
    lics = LicLicense.query.filter(
        LicLicense.company_id == company_id,
        LicLicense.expires_at >= _date.today(),
    ).all()
    for lic in lics:
        lic.status = "active"
    db.session.commit()
    _log_activity(user, "company_reactivated", "company", company_id)
    _log_license_events(user, "license_reactivated", lics)
    return jsonify(result)


@admin_lic_bp.route("/companies/<int:company_id>/reset-password", methods=["POST"])
def reset_company_admin_password(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    new_password = (data.get("new_password") or "").strip()
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"}), 400

    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash(new_password)

    updated = LicCompanyUser.query.filter_by(company_id=company_id).all()
    for cu in updated:
        cu.password_hash = new_hash
    db.session.commit()

    if updated:
        _log_activity(user, "company_admin_password_reset", "company", company_id, {"emails": [u.email for u in updated]})
        return jsonify({"success": True, "message": "تمت إعادة تعيين كلمة مرور مدير الشركة", "users": [u.email for u in updated]})

    return jsonify({"success": False, "message": "لا يوجد حساب مدير لهذه الشركة"}), 404


@admin_lic_bp.route("/companies/<int:company_id>/revoke-license", methods=["POST"])
def revoke_company_license(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404
    affected = LicLicense.query.filter(
        LicLicense.company_id == company_id,
        LicLicense.status.in_(["active", "suspended"]),
    ).all()
    result = revoke_license(company_id)
    if result["success"]:
        _log_activity(user, "license_revoked", "company", company_id, {"revoked": result.get("revoked", 0)})
        _log_license_events(user, "license_revoked", affected)
    return jsonify(result)


# ── Lists ───────────────────────────────────────────────────

@admin_lic_bp.route("/subscriptions")
def list_subscriptions():
    user, err = _admin_or_abort()
    if err:
        return err
    status = request.args.get("status")
    subs = LicSubscription.query.order_by(LicSubscription.id.desc()).all()
    if status in ("grace", "expired"):
        subs = [s for s in subs if s.check_status() == status]
    elif status:
        subs = [s for s in subs if s.status == status]
    return jsonify({"success": True, "subscriptions": [s.to_dict() for s in subs]})


@admin_lic_bp.route("/licenses")
def list_licenses():
    user, err = _admin_or_abort()
    if err:
        return err
    status = request.args.get("status")
    query = LicLicense.query
    if status:
        query = query.filter_by(status=status)
    return jsonify({"success": True, "licenses": [l.to_dict() for l in query.order_by(LicLicense.id.desc()).all()]})


@admin_lic_bp.route("/licenses/<int:license_id>")
def license_detail(license_id):
    user, err = _admin_or_abort()
    if err:
        return err
    lic = db.session.get(LicLicense, license_id)
    if not lic:
        return jsonify({"success": False, "message": "License not found"}), 404
    d = lic.to_dict()
    company = db.session.get(LicCompany, lic.company_id)
    sub = db.session.get(LicSubscription, lic.subscription_id) if lic.subscription_id else None
    d["company"] = company.to_dict() if company else None
    d["plan"] = sub.plan.to_dict() if (sub and sub.plan) else None
    history = LicActivityLog.query.filter_by(target_type="license", target_id=license_id).order_by(LicActivityLog.id.desc()).limit(50).all()
    d["history"] = [h.to_dict() for h in history]
    return jsonify({"success": True, "license": d})


@admin_lic_bp.route("/payments")
def list_payments():
    user, err = _admin_or_abort()
    if err:
        return err
    status = request.args.get("status")
    query = LicPayment.query
    if status:
        query = query.filter_by(status=status)
    return jsonify({"success": True, "payments": [p.to_dict() for p in query.order_by(LicPayment.id.desc()).all()]})


@admin_lic_bp.route("/plans")
def list_plans():
    user, err = _admin_or_abort()
    if err:
        return err
    return jsonify({"success": True, "plans": [p.to_dict() for p in LicPlan.query.order_by(LicPlan.sort_order).all()]})


# ── Company Edit ─────────────────────────────────────────────

@admin_lic_bp.route("/companies/<int:company_id>", methods=["PUT"])
def update_company(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    data = request.get_json(silent=True) or {}
    for field in ("name", "name_ar", "email", "phone", "address", "tax_number", "port"):
        if field in data:
            setattr(company, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "company": company.to_dict()})


@admin_lic_bp.route("/companies/<int:company_id>", methods=["DELETE"])
def delete_company(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404
    company.status = "deleted"
    db.session.commit()
    return jsonify({"success": True, "message": f"Company '{company.name}' deleted"})


# ── Company Databases ────────────────────────────────────────

@admin_lic_bp.route("/databases")
def list_databases():
    user, err = _admin_or_abort()
    if err:
        return err
    status = request.args.get("status")
    from licensing.db_manager import test_company_db, get_db_size
    companies = LicCompany.query.filter(LicCompany.status != "deleted").order_by(LicCompany.id.desc()).all()
    items = []
    for c in companies:
        reg = LicDatabaseRegistry.query.filter_by(company_id=c.id).order_by(LicDatabaseRegistry.id.desc()).first()
        entry = {
            "company_id": c.id, "company_name": c.name,
            "db_name": None, "status": "none", "size_mb": None,
            "created_at": None, "last_migration": None, "connected": False,
        }
        if reg:
            entry.update({
                "db_name": reg.db_name, "status": reg.status,
                "size_mb": float(reg.size_mb) if reg.size_mb else None,
                "created_at": reg.created_at.isoformat() if reg.created_at else None,
                "last_migration": reg.last_migration.isoformat() if reg.last_migration else None,
            })
            entry["connected"] = test_company_db(c)
            if entry["connected"] and entry["size_mb"] is None:
                size = get_db_size(c)
                if size:
                    reg.size_mb = round(size, 2)
                    db.session.commit()
                    entry["size_mb"] = float(reg.size_mb)
        if status and entry["status"] != status:
            continue
        items.append(entry)
    return jsonify({"success": True, "databases": items})


@admin_lic_bp.route("/companies/<int:company_id>/provision-db", methods=["POST"])
def provision_company_db(company_id):
    user, err = _admin_or_abort()
    if err:
        return err
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404
    from licensing.db_manager import create_company_db, get_company_engine
    ok = create_company_db(company)
    if not ok:
        _log_activity(user, "company_db_failed", "company", company_id, {"db": company.db_name})
        return jsonify({"success": False, "message": "تعذر إنشاء قاعدة البيانات — تأكد من صلاحية CREATE DATABASE لحساب قاعدة البيانات، ثم أعد المحاولة."}), 502
    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            for cu in LicCompanyUser.query.filter_by(company_id=company_id).all():
                exists = conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": cu.email}).scalar()
                if not exists:
                    conn.execute(text(
                        "INSERT INTO users (username, email, password_hash, full_name, role, is_active) "
                        "VALUES (:u, :e, :p, :n, 'admin', true)"
                    ), {
                        "u": cu.email.split("@")[0], "e": cu.email,
                        "p": cu.password_hash, "n": cu.full_name or cu.email,
                    })
            conn.commit()
    except Exception as e:
        log.warning("User sync into company DB %d failed: %s", company_id, e)
    _log_activity(user, "company_db_provisioned", "company", company_id, {"db": company.db_name})
    return jsonify({"success": True, "message": f"Database '{company.db_name}' ready"})


# ── Master Users ─────────────────────────────────────────────

@admin_lic_bp.route("/users")
def list_master_users():
    user, err = _admin_or_abort()
    if err:
        return err
    users = LicMasterUser.query.order_by(LicMasterUser.id.desc()).all()
    return jsonify({"success": True, "users": [u.to_dict() for u in users]})


@admin_lic_bp.route("/users", methods=["POST"])
def create_master_user():
    user, err = _admin_or_abort()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400
    if LicMasterUser.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already exists"}), 400
    from werkzeug.security import generate_password_hash
    new_user = LicMasterUser(
        email=email, password_hash=generate_password_hash(password),
        full_name=data.get("full_name", ""),
        role=data.get("role", "support"),
        is_active=True,
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": True, "user": new_user.to_dict()})


@admin_lic_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_master_user(user_id):
    user, err = _admin_or_abort()
    if err:
        return err
    target = db.session.get(LicMasterUser, user_id)
    if not target:
        return jsonify({"success": False, "message": "User not found"}), 404
    target.is_active = not target.is_active
    db.session.commit()
    return jsonify({"success": True, "user": target.to_dict()})


# ── Subscription Actions ─────────────────────────────────────

@admin_lic_bp.route("/subscriptions/<int:sub_id>/renew", methods=["POST"])
def renew_subscription_action(sub_id):
    user, err = _admin_or_abort()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    days = data.get("days", 365)
    sub = db.session.get(LicSubscription, sub_id)
    if not sub:
        return jsonify({"success": False, "message": "Subscription not found"}), 404
    renewed = renew_subscription(sub.id, days)
    if not renewed:
        return jsonify({"success": False, "message": "Renewal failed"}), 500
    lic = LicLicense.query.filter_by(company_id=sub.company_id).order_by(LicLicense.id.desc()).first()
    if lic:
        _log_activity(user, "license_renewed", target_type="license", target_id=lic.id, details={"days": days})
    return jsonify({"success": True, "subscription": renewed.to_dict()})


@admin_lic_bp.route("/subscriptions/<int:sub_id>/plan", methods=["POST"])
def change_subscription_plan(sub_id):
    user, err = _admin_or_abort()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    new_plan_code = (data.get("plan_code") or "").strip()
    sub = db.session.get(LicSubscription, sub_id)
    if not sub:
        return jsonify({"success": False, "message": "Subscription not found"}), 404
    if not new_plan_code:
        return jsonify({"success": False, "message": "plan_code is required"}), 400
    new_plan = LicPlan.query.filter_by(code=new_plan_code, is_active=True).first()
    if not new_plan:
        return jsonify({"success": False, "message": f"Plan '{new_plan_code}' not found"}), 404
    old_code = sub.plan.code if sub.plan else None
    sub.plan_id = new_plan.id
    db.session.commit()
    _log_activity(user, "subscription_plan_changed", target_type="subscription", target_id=sub.id,
                  details={"from": old_code, "to": new_plan.code})
    return jsonify({"success": True, "message": f"Plan changed {old_code} → {new_plan.code}", "subscription": sub.to_dict()})


@admin_lic_bp.route("/subscriptions/<int:sub_id>/cancel", methods=["POST"])
def cancel_subscription_action(sub_id):
    user, err = _admin_or_abort()
    if err:
        return err
    sub = db.session.get(LicSubscription, sub_id)
    if not sub:
        return jsonify({"success": False, "message": "Subscription not found"}), 404
    sub.status = "cancelled"
    db.session.commit()
    _log_activity(user, "subscription_cancelled", target_type="subscription", target_id=sub.id)
    return jsonify({"success": True, "message": "Subscription cancelled", "subscription": sub.to_dict()})


# ── Payment Record ───────────────────────────────────────────

@admin_lic_bp.route("/payments", methods=["POST"])
def record_payment():
    user, err = _admin_or_abort()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    company_id = data.get("company_id")
    amount = data.get("amount")
    if not company_id or not amount:
        return jsonify({"success": False, "message": "company_id and amount required"}), 400
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404
    sub = company.active_subscription
    payment = LicPayment(
        company_id=company_id,
        subscription_id=sub.id if sub else None,
        amount=amount,
        currency=data.get("currency", "EGP"),
        payment_method=data.get("payment_method", "cash"),
        reference_no=data.get("reference_no", ""),
        status=data.get("status", "confirmed"),
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify({"success": True, "payment": payment.to_dict()})


@admin_lic_bp.route("/payments/<int:payment_id>/mark-paid", methods=["POST"])
def mark_payment_paid(payment_id):
    user, err = _admin_or_abort()
    if err:
        return err
    payment = db.session.get(LicPayment, payment_id)
    if not payment:
        return jsonify({"success": False, "message": "Payment not found"}), 404
    if payment.status != "confirmed":
        from datetime import datetime as _dt
        payment.status = "confirmed"
        payment.paid_at = _dt.utcnow()
        payment.confirmed_by = user.email
        db.session.commit()
        _log_activity(user, "payment_confirmed", target_type="payment", target_id=payment.id,
                      details={"amount": float(payment.amount), "currency": payment.currency})
    return jsonify({"success": True, "payment": payment.to_dict()})


# ── Activity Log ─────────────────────────────────────────────

@admin_lic_bp.route("/activity")
def activity_log():
    user, err = _admin_or_abort()
    if err:
        return err
    from licensing.models import LicActivityLog
    logs = LicActivityLog.query.order_by(LicActivityLog.id.desc()).limit(100).all()
    return jsonify({"success": True, "activities": [l.to_dict() for l in logs]})


# ── Reports ────────────────────────────────────────────────

@admin_lic_bp.route("/reports")
def reports():
    user, err = _admin_or_abort()
    if err:
        return err
    from collections import Counter
    from datetime import datetime as _dt

    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months = months[::-1]
    month_set = set(months)
    revenue_by_month = {m: 0.0 for m in months}
    companies_by_month = {m: 0 for m in months}

    payments = LicPayment.query.all()
    for p in payments:
        if p.status != "confirmed":
            continue
        d = p.paid_at or p.created_at
        key = f"{d.year:04d}-{d.month:02d}" if d is not None else None
        if key in month_set:
            revenue_by_month[key] += float(p.amount)

    companies = LicCompany.query.all()
    for c in companies:
        if c.created_at:
            key = f"{c.created_at.year:04d}-{c.created_at.month:02d}"
            if key in month_set:
                companies_by_month[key] += 1

    comp_status = Counter(c.status for c in companies if c.status != "deleted")
    sub_counter = Counter(s.check_status() for s in LicSubscription.query.all())
    lic_counter = Counter(l.status for l in LicLicense.query.all())

    plan_rev = {}
    plan_comp = Counter()
    for s in LicSubscription.query.all():
        pcode = s.plan.code if s.plan else None
        plan_comp[pcode or "—"] += 1
        if pcode and (pcode not in plan_rev):
            plan_rev[pcode] = {"revenue": 0.0, "count": 0}
        if pcode:
            plan_rev[pcode]["count"] += 1
    for p in payments:
        if p.status != "confirmed" or not p.subscription_id:
            continue
        sub = db.session.get(LicSubscription, p.subscription_id)
        pcode = sub.plan.code if (sub and sub.plan) else None
        key = pcode or "—"
        if key not in plan_rev:
            plan_rev[key] = {"revenue": 0.0, "count": 0}
        plan_rev[key]["revenue"] += float(p.amount)

    pending_total = sum(float(p.amount) for p in payments if p.status == "pending")

    top_by_rev = Counter()
    for p in payments:
        if p.status != "confirmed":
            continue
        top_by_rev[p.company_id] += float(p.amount)
    top_companies = []
    for cid, amt in top_by_rev.most_common(5):
        c = db.session.get(LicCompany, cid)
        top_companies.append({"company_id": cid, "company_name": c.name if c else str(cid), "revenue": round(amt, 2)})

    return jsonify({
        "success": True,
        "months": months,
        "revenue_by_month": revenue_by_month,
        "companies_by_month": companies_by_month,
        "company_status": dict(comp_status),
        "subscription_status": dict(sub_counter),
        "license_status": dict(lic_counter),
        "plan_distribution": dict(plan_comp),
        "revenue_by_plan": plan_rev,
        "pending_total": round(pending_total, 2),
        "top_companies": top_companies,
    })


# ── Settings ────────────────────────────────────────────────

@admin_lic_bp.route("/settings")
def system_settings():
    user, err = _admin_or_abort()
    if err:
        return err
    from licensing.plans_data import TRIAL_DAYS, GRACE_PERIOD_DAYS
    u = db.engine.url
    return jsonify({
        "success": True,
        "settings": {
            "trial_days": TRIAL_DAYS,
            "grace_days": GRACE_PERIOD_DAYS,
            "db": {
                "host": u.host or "localhost",
                "port": u.port or 5432,
                "database": u.database,
                "user": u.username,
            },
            "counts": {
                "plans": LicPlan.query.count(),
                "companies": LicCompany.query.filter(LicCompany.status != "deleted").count(),
                "active_subscriptions": sum(1 for s in LicSubscription.query.all() if s.check_status() in ("trial", "active")),
                "active_licenses": LicLicense.query.filter_by(status="active").count(),
                "payments_confirmed": LicPayment.query.filter_by(status="confirmed").count(),
                "master_users": LicMasterUser.query.count(),
                "company_users": LicCompanyUser.query.count(),
            },
        },
    })


@admin_lic_bp.route("/change-password", methods=["POST"])
def change_master_password():
    user, err = _admin_or_abort()
    if err:
        return err
    from werkzeug.security import check_password_hash, generate_password_hash
    data = request.get_json(silent=True) or {}
    old_pw = (data.get("old_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()
    if not old_pw:
        return jsonify({"success": False, "message": "كلمة المرور الحالية مطلوبة"}), 400
    if len(new_pw) < 6:
        return jsonify({"success": False, "message": "كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"}), 400
    if not check_password_hash(user.password_hash, old_pw):
        return jsonify({"success": False, "message": "كلمة المرور الحالية غير صحيحة"}), 400
    user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    _log_activity(user, "master_password_changed")
    return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})


# ═══════════════════════════════════════════════════════════════
# Company Auth API — /logout, /me, /access
# (Login is handled by routes/auth.py → detects LicCompanyUser)
# ═══════════════════════════════════════════════════════════════

company_auth_bp = Blueprint("company_auth", __name__)


@company_auth_bp.route("/logout", methods=["POST"])
def company_logout():
    from licensing.auth import logout_company_user, is_company_user_logged_in
    if is_company_user_logged_in():
        logout_company_user()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Not logged in as company user"}), 401


@company_auth_bp.route("/api/me")
def company_me():
    from licensing.auth import get_company_session_data, is_company_user_logged_in
    if not is_company_user_logged_in():
        return jsonify({"authenticated": False}), 401
    data = get_company_session_data()
    return jsonify({"authenticated": True, **data})


@company_auth_bp.route("/api/company/access")
def company_access_check():
    """Check if current company user has valid subscription/license."""
    from licensing.auth import is_company_user_logged_in
    if not is_company_user_logged_in():
        return jsonify({"allowed": False}), 401
    company_id = session.get("lic_company_id")
    from licensing.engine import can_access as _can_access
    return jsonify(_can_access(company_id))


@company_auth_bp.route("/api/company/db-test")
def company_db_test():
    """Test connection to the current company's DB."""
    from licensing.auth import is_company_user_logged_in
    if not is_company_user_logged_in():
        return jsonify({"success": False}), 401
    company_id = session.get("lic_company_id")
    company = db.session.get(LicCompany, company_id)
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404
    from licensing.db_manager import test_company_db
    ok = test_company_db(company)
    return jsonify({"success": ok, "db_name": company.db_name})
