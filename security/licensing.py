# -*- coding: utf-8 -*-
"""Licensing lifecycle functions (Phase 3).

Provides high-level operations for Plans, Trials, Subscriptions, and Licenses
that compose the existing engine functions with RBAC + audit logging.

All functions return dict {success, message, ...} and record audit trails.
"""
import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)


def create_plan(name, name_ar, code, price_monthly=None, price_yearly=None,
                max_users=5, max_projects=10, max_storage_mb=1024,
                modules=None, sort_order=0, actor_email=None, actor_id=None, ip=None):
    """Create a new plan with audit logging."""
    from database import db
    from licensing.models import LicPlan
    from security.audit import record as audit_record

    if LicPlan.query.filter_by(code=code).first():
        return {"success": False, "message": f"الباقة '{code}' موجودة مسبقاً"}

    plan = LicPlan(
        code=code, name=name, name_ar=name_ar,
        price_monthly=price_monthly, price_yearly=price_yearly,
        max_users=max_users, max_projects=max_projects,
        max_storage_mb=max_storage_mb, modules=modules or {},
        sort_order=sort_order, is_active=True,
    )
    db.session.add(plan)
    db.session.commit()

    audit_record(action="PLAN_CREATED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="plan",
                 resource_id=plan.id, ip=ip, new_value=name, result="SUCCESS")
    log.info("Created plan %s (id=%d)", code, plan.id)
    return {"success": True, "plan": plan.to_dict(), "message": f"تم إنشاء الباقة '{name}'"}


def update_plan(plan_id, updates, actor_email=None, actor_id=None, ip=None):
    """Update plan fields with audit logging."""
    from database import db
    from licensing.models import LicPlan
    from security.audit import record as audit_record

    plan = db.session.get(LicPlan, plan_id)
    if not plan:
        return {"success": False, "message": "الباقة غير موجودة"}

    old_values = {}
    for field in ["name", "name_ar", "price_monthly", "price_yearly",
                  "max_users", "max_projects", "max_storage_mb",
                  "modules", "sort_order", "is_active"]:
        if field in updates:
            old_values[field] = str(getattr(plan, field))
            setattr(plan, field, updates[field])

    db.session.commit()
    audit_record(action="PLAN_UPDATED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="plan",
                 resource_id=plan.id, ip=ip,
                 old_value=str(old_values), new_value=str(updates), result="SUCCESS")
    log.info("Updated plan %d: %s", plan_id, list(updates.keys()))
    return {"success": True, "plan": plan.to_dict(), "message": "تم تحديث الباقة"}


def extend_trial(company_id, days, actor_email=None, actor_id=None, ip=None):
    """Extend a trial subscription by N days."""
    from database import db
    from licensing.models import LicCompany, LicSubscription, LicLicense
    from licensing.engine import create_license
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active"]),
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return {"success": False, "message": "لا يوجد اشتراك تجريبي"}

    old_end = sub.end_date
    sub.end_date = sub.end_date + timedelta(days=days)
    if company.trial_ends_at:
        company.trial_ends_at = company.trial_ends_at + timedelta(days=days)

    # Sync license expiry
    lic = LicLicense.query.filter_by(
        company_id=company_id, subscription_id=sub.id, status="active"
    ).first()
    if lic:
        lic.expires_at = sub.end_date

    db.session.commit()
    audit_record(action="TRIAL_EXTENDED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="subscription",
                 resource_id=sub.id, company_id=company_id, ip=ip,
                 old_value=str(old_end), new_value=str(sub.end_date), result="SUCCESS")
    log.info("Extended trial for company %d by %d days (now %s)", company_id, days, sub.end_date)
    return {"success": True, "subscription": sub.to_dict(), "message": f"تم تمديد الفترة التجريبية {days} يوماً"}


def end_trial(company_id, actor_email=None, actor_id=None, ip=None):
    """End a trial subscription immediately (set end_date to today)."""
    from database import db
    from licensing.models import LicCompany, LicSubscription
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status == "trial",
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return {"success": False, "message": "لا يوجد اشتراك تجريبي"}

    old_end = sub.end_date
    sub.end_date = date.today()
    company.is_trial = False
    company.trial_ends_at = None
    db.session.commit()

    audit_record(action="TRIAL_ENDED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="subscription",
                 resource_id=sub.id, company_id=company_id, ip=ip,
                 old_value=str(old_end), new_value=str(date.today()), result="SUCCESS")
    log.info("Ended trial for company %d", company_id)
    return {"success": True, "subscription": sub.to_dict(), "message": "تم إنهاء الفترة التجريبية"}


def convert_trial_to_paid(company_id, plan_code, subscription_days=365,
                          actor_email=None, actor_id=None, ip=None):
    """Convert a trial subscription to a paid one."""
    from database import db
    from licensing.models import LicCompany, LicSubscription, LicLicense, LicPlan
    from licensing.engine import create_license
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    plan = LicPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not plan:
        return {"success": False, "message": f"الباقة '{plan_code}' غير موجودة"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active"]),
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return {"success": False, "message": "لا يوجد اشتراك"}

    old_status = sub.status
    old_plan = sub.plan.code if sub.plan else None

    today = date.today()
    sub.plan_id = plan.id
    sub.end_date = today + timedelta(days=subscription_days)
    sub.status = "active"
    company.is_trial = False
    company.trial_ends_at = None

    # Update or create license
    lic = LicLicense.query.filter_by(
        company_id=company_id, subscription_id=sub.id, status="active"
    ).first()
    if lic:
        lic.expires_at = sub.end_date
        lic.status = "active"
    else:
        create_license(company_id, sub.id, subscription_days)

    db.session.commit()
    audit_record(action="TRIAL_CONVERTED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="subscription",
                 resource_id=sub.id, company_id=company_id, ip=ip,
                 old_value=f"{old_status}/{old_plan}", new_value=f"active/{plan_code}",
                 result="SUCCESS")
    log.info("Converted trial for company %d to paid plan %s", company_id, plan_code)
    return {"success": True, "subscription": sub.to_dict(), "plan": plan.to_dict(),
            "message": f"تم تحويل الاشتراك إلى الباقة المدفوعة '{plan.name}'"}


def cancel_subscription(company_id, actor_email=None, actor_id=None, ip=None):
    """Cancel a subscription + revoke active licenses."""
    from database import db
    from licensing.models import LicCompany, LicSubscription, LicLicense
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active", "grace"]),
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return {"success": False, "message": "لا يوجد اشتراك نشط"}

    old_status = sub.status
    sub.status = "cancelled"

    # Revoke active licenses
    lics = LicLicense.query.filter_by(company_id=company_id, status="active").all()
    for lic in lics:
        lic.status = "revoked"

    db.session.commit()
    audit_record(action="SUBSCRIPTION_CANCELLED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="subscription",
                 resource_id=sub.id, company_id=company_id, ip=ip,
                 old_value=old_status, new_value="cancelled", result="SUCCESS")
    log.info("Cancelled subscription for company %d", company_id)
    return {"success": True, "message": "تم إلغاء الاشتراك"}


def suspend_license_for_company(company_id, actor_email=None, actor_id=None, ip=None):
    """Suspend all active licenses with audit logging."""
    from database import db
    from licensing.models import LicCompany, LicLicense
    from licensing.engine import suspend_license
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    affected = LicLicense.query.filter_by(company_id=company_id, status="active").all()
    result = suspend_license(company_id)

    audit_record(action="LICENSES_SUSPENDED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="license",
                 company_id=company_id, ip=ip,
                 old_value=str(len(affected)), new_value="suspended",
                 result="SUCCESS")
    log.info("Suspended %d licenses for company %d", len(affected), company_id)
    return result


def revoke_license_for_company(company_id, actor_email=None, actor_id=None, ip=None):
    """Revoke all active/suspended licenses with audit logging."""
    from database import db
    from licensing.models import LicCompany, LicLicense
    from licensing.engine import revoke_license
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    affected = LicLicense.query.filter(
        LicLicense.company_id == company_id,
        LicLicense.status.in_(["active", "suspended"]),
    ).all()
    result = revoke_license(company_id)

    audit_record(action="LICENSES_REVOKED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="license",
                 company_id=company_id, ip=ip,
                 old_value=str(len(affected)), new_value="revoked",
                 result="SUCCESS")
    log.info("Revoked %d licenses for company %d", len(affected), company_id)
    return result


def renew_subscription_for_company(company_id, days=365, actor_email=None, actor_id=None, ip=None):
    """Renew a subscription + license with audit logging."""
    from database import db
    from licensing.models import LicCompany, LicSubscription
    from licensing.engine import renew_subscription
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active", "grace", "expired"]),
    ).order_by(LicSubscription.id.desc()).first()

    if not sub:
        return {"success": False, "message": "لا يوجد اشتراك"}

    old_end = sub.end_date
    renewed = renew_subscription(sub.id, days)
    if not renewed:
        return {"success": False, "message": "فشلت عملية التجديد"}

    audit_record(action="SUBSCRIPTION_RENEWED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="subscription",
                 resource_id=sub.id, company_id=company_id, ip=ip,
                 old_value=str(old_end), new_value=str(renewed.end_date), result="SUCCESS")
    log.info("Renewed subscription for company %d: %s → %s", company_id, old_end, renewed.end_date)
    return {"success": True, "subscription": renewed.to_dict(),
            "message": f"تم تجديد الاشتراك {days} يوماً"}
