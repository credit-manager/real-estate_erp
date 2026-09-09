# -*- coding: utf-8 -*-
"""License and subscription validation for DynamicPro ERP."""
import logging
import secrets
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import db
from licensing.models import LicCompany, LicLicense, LicSubscription, LicPlan
from licensing.plans_data import GRACE_PERIOD_DAYS

log = logging.getLogger(__name__)


def generate_license_key():
    """Generate a unique, high-entropy human-readable license key."""
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"LIC-{'-'.join(parts)}"


def check_subscription(company_id: int) -> dict:
    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"allowed": False, "status": "none", "days_left": None, "warning": None}

    sub = (
        LicSubscription.query.filter(
            LicSubscription.company_id == company_id,
            LicSubscription.status.in_(["trial", "active", "grace"]),
        )
        .order_by(LicSubscription.id.desc())
        .first()
    )
    if not sub:
        return {"allowed": False, "status": "none", "days_left": None, "warning": None}

    computed = sub.check_status()
    today = date.today()
    if computed in ("trial", "active"):
        days_left = (sub.end_date - today).days
        if days_left <= 7:
            warning = f"اشتراكك سينتهي خلال {days_left} أيام!"
        elif days_left <= 30:
            warning = f"اشتراكك سينتهي خلال {days_left} يوماً. يرجى التجديد."
        else:
            warning = None
        return {"allowed": True, "status": computed, "days_left": days_left, "warning": warning}

    if computed == "grace":
        grace_end = sub.end_date + timedelta(days=GRACE_PERIOD_DAYS)
        days_left = (grace_end - today).days
        return {
            "allowed": True,
            "status": "grace",
            "days_left": days_left,
            "warning": f"اشتراكك انتهى. لديك {days_left} أيام متبقية للتجديد.",
        }

    return {"allowed": False, "status": computed, "days_left": None, "warning": "انتهى اشتراكك. يرجى التجديد."}


def check_license(company_id: int) -> dict:
    """Validate company and license state, including the license expiration date."""
    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"allowed": False, "status": "none", "warning": None}

    if company.status == "suspended":
        return {"allowed": False, "status": "suspended", "warning": "تم تعليق حسابك إدارياً."}
    if company.status == "deleted":
        return {"allowed": False, "status": "revoked", "warning": "تم حذف هذا الحساب."}

    lic = (
        LicLicense.query.filter(LicLicense.company_id == company_id)
        .order_by(LicLicense.id.desc())
        .first()
    )
    if not lic:
        return {"allowed": False, "status": "none", "warning": "لا يوجد ترخيص."}

    if lic.status == "suspended":
        return {"allowed": False, "status": "suspended", "warning": "تم تعليق الترخيص."}
    if lic.status == "revoked":
        return {"allowed": False, "status": "revoked", "warning": "تم إلغاء الترخيص."}

    today = date.today()
    if lic.expires_at and lic.expires_at < today:
        return {"allowed": False, "status": "expired", "warning": "انتهت صلاحية الترخيص. يرجى التجديد."}

    if lic.status != "active":
        return {"allowed": False, "status": lic.status or "inactive", "warning": "الترخيص غير مفعّل."}

    return {"allowed": True, "status": "active", "warning": None}


def can_access(company_id: int) -> dict:
    sub = check_subscription(company_id)
    lic = check_license(company_id)
    return {
        "allowed": sub["allowed"] and lic["allowed"],
        "subscription": sub,
        "license": lic,
        "warning": sub.get("warning") or lic.get("warning"),
    }


def create_license(company_id: int, subscription_id: int, days: int) -> LicLicense:
    if days <= 0:
        raise ValueError("License duration must be greater than zero")

    today = date.today()
    for _ in range(5):
        key = generate_license_key()
        lic = LicLicense(
            company_id=company_id,
            subscription_id=subscription_id,
            license_key=key,
            status="active",
            issued_at=today,
            expires_at=today + timedelta(days=days),
        )
        try:
            db.session.add(lic)
            db.session.commit()
            log.info("Created license %s for company %d (%d days)", key, company_id, days)
            return lic
        except IntegrityError:
            db.session.rollback()
            continue
    raise RuntimeError("Could not generate a unique license key")


def renew_subscription(subscription_id: int, days: int) -> LicSubscription:
    """Extend from the current expiration, preserving prepaid time."""
    if days <= 0:
        raise ValueError("Renewal duration must be greater than zero")

    sub = db.session.get(LicSubscription, subscription_id)
    if not sub:
        return None

    today = date.today()
    base_date = max(today, sub.end_date or today)
    sub.end_date = base_date + timedelta(days=days)
    sub.status = "active"

    lic = (
        LicLicense.query.filter_by(company_id=sub.company_id, subscription_id=sub.id)
        .order_by(LicLicense.id.desc())
        .first()
    )
    if lic:
        license_base = max(today, lic.expires_at or today)
        lic.expires_at = license_base + timedelta(days=days)
        lic.status = "active"
    else:
        create_license(sub.company_id, sub.id, days)

    db.session.commit()
    log.info("Renewed subscription %d until %s", subscription_id, sub.end_date)
    return sub


def suspend_license(company_id: int) -> dict:
    lics = LicLicense.query.filter_by(company_id=company_id, status="active").all()
    for lic in lics:
        lic.status = "suspended"
    db.session.commit()
    log.info("Suspended %d licenses for company %d", len(lics), company_id)
    return {"success": True, "suspended": len(lics)}


def revoke_license(company_id: int) -> dict:
    lics = LicLicense.query.filter(
        LicLicense.company_id == company_id,
        LicLicense.status.in_(["active", "suspended"]),
    ).all()
    for lic in lics:
        lic.status = "revoked"
    db.session.commit()
    log.info("Revoked %d licenses for company %d", len(lics), company_id)
    return {"success": True, "revoked": len(lics)}


def check_module_access(company_id: int, module: str) -> bool:
    if not module:
        return False
    access = can_access(company_id)
    if not access["allowed"]:
        return False

    sub = (
        LicSubscription.query.filter(
            LicSubscription.company_id == company_id,
            LicSubscription.status.in_(["trial", "active", "grace"]),
        )
        .order_by(LicSubscription.id.desc())
        .first()
    )
    if not sub:
        return False

    plan = db.session.get(LicPlan, sub.plan_id) if sub.plan_id else None
    if not plan:
        return False
    return bool((plan.modules or {}).get(module, False))


def check_user_limit(company_id: int) -> dict:
    access = can_access(company_id)
    if not access["allowed"]:
        return {"within_limit": False, "current": 0, "max": 0}

    sub = (
        LicSubscription.query.filter(
            LicSubscription.company_id == company_id,
            LicSubscription.status.in_(["trial", "active", "grace"]),
        )
        .order_by(LicSubscription.id.desc())
        .first()
    )
    if not sub:
        return {"within_limit": False, "current": 0, "max": 0}

    plan = db.session.get(LicPlan, sub.plan_id) if sub.plan_id else None
    if not plan:
        return {"within_limit": False, "current": 0, "max": 0}

    max_users = plan.max_users
    if max_users == -1:
        return {"within_limit": True, "current": 0, "max": -1}

    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
            current = result.scalar() or 0
    except Exception:
        current = 0

    return {"within_limit": current < max_users, "current": current, "max": max_users}
