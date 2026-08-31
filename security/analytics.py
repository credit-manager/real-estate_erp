# -*- coding: utf-8 -*-
"""Platform analytics: company stats, revenue, usage, module adoption.

Provides data for the Control Center dashboard and analytics views.
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def platform_overview():
    """Platform-wide KPIs for the main dashboard."""
    from database import db
    from licensing.models import LicCompany, LicSubscription, LicLicense, LicPayment, LicMasterUser
    from security.models import ModuleCatalog, CompanyModule, MasterSession, SecurityEvent
    from sqlalchemy import func

    now = datetime.utcnow()
    last_30d = now - timedelta(days=30)
    last_90d = now - timedelta(days=90)

    # Companies
    total_companies = LicCompany.query.count()
    active_companies = LicCompany.query.filter_by(status="active").count()
    trial_companies = LicCompany.query.filter_by(status="trial").count()
    suspended_companies = LicCompany.query.filter_by(status="suspended").count()

    # Subscriptions
    active_subscriptions = LicSubscription.query.filter_by(status="active").count()
    trial_subscriptions = LicSubscription.query.filter_by(status="trial").count()
    expired_subscriptions = LicSubscription.query.filter_by(status="expired").count()

    # Licenses
    active_licenses = LicLicense.query.filter_by(status="active").count()

    # Revenue
    total_revenue = db.session.query(func.sum(LicPayment.amount)).filter(
        LicPayment.status == "confirmed"
    ).scalar() or 0

    revenue_30d = db.session.query(func.sum(LicPayment.amount)).filter(
        LicPayment.status == "confirmed",
        LicPayment.created_at >= last_30d,
    ).scalar() or 0

    revenue_90d = db.session.query(func.sum(LicPayment.amount)).filter(
        LicPayment.status == "confirmed",
        LicPayment.created_at >= last_90d,
    ).scalar() or 0

    # Users
    total_master_users = LicMasterUser.query.filter_by(is_active=True).count()

    # Modules
    total_modules = ModuleCatalog.query.filter_by(is_active=True).count()
    total_company_modules = CompanyModule.query.filter_by(enabled=True).count()

    # Sessions & Security
    active_sessions = MasterSession.query.filter_by(revoked=False).count()
    security_alerts_24h = SecurityEvent.query.filter(
        SecurityEvent.severity.in_(["warning", "critical"]),
        SecurityEvent.created_at >= now - timedelta(hours=24),
    ).count()

    return {
        "success": True,
        "companies": {
            "total": total_companies,
            "active": active_companies,
            "trial": trial_companies,
            "suspended": suspended_companies,
        },
        "subscriptions": {
            "active": active_subscriptions,
            "trial": trial_subscriptions,
            "expired": expired_subscriptions,
        },
        "licenses": {
            "active": active_licenses,
        },
        "revenue": {
            "total": float(total_revenue),
            "last_30d": float(revenue_30d),
            "last_90d": float(revenue_90d),
        },
        "users": {
            "master": total_master_users,
        },
        "modules": {
            "catalog_count": total_modules,
            "company_module_grants": total_company_modules,
        },
        "security": {
            "active_sessions": active_sessions,
            "alerts_24h": security_alerts_24h,
        },
    }


def company_analytics(company_id):
    """Detailed analytics for a single company."""
    from database import db
    from licensing.models import LicCompany, LicSubscription, LicLicense, LicPayment
    from security.models import CompanyModule
    from sqlalchemy import func

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    subscription = LicSubscription.query.filter_by(company_id=company_id).first()
    license_ = LicLicense.query.filter_by(company_id=company_id).first()

    # Revenue
    total_paid = db.session.query(func.sum(LicPayment.amount)).filter(
        LicPayment.company_id == company_id,
        LicPayment.status == "confirmed",
    ).scalar() or 0

    payment_count = LicPayment.query.filter_by(company_id=company_id).count()

    # Modules
    enabled_modules = CompanyModule.query.filter_by(company_id=company_id, enabled=True).all()

    return {
        "success": True,
        "company": company.to_dict(),
        "subscription": subscription.to_dict() if subscription else None,
        "license": license_.to_dict() if license_ else None,
        "revenue": {
            "total_paid": float(total_paid),
            "payment_count": payment_count,
        },
        "modules_enabled": [m.module_code for m in enabled_modules],
        "module_count": len(enabled_modules),
    }


def revenue_analytics():
    """Revenue breakdown and trends."""
    from database import db
    from licensing.models import LicPayment, LicCompany
    from sqlalchemy import func

    now = datetime.utcnow()
    months = []
    for i in range(11, -1, -1):
        d = now - timedelta(days=30 * i)
        months.append(d.strftime("%Y-%m"))

    monthly = []
    for ym in months:
        year, month = int(ym[:4]), int(ym[5:7])
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        total = db.session.query(func.sum(LicPayment.amount)).filter(
            LicPayment.status == "confirmed",
            LicPayment.created_at >= start,
            LicPayment.created_at < end,
        ).scalar() or 0
        monthly.append({"month": ym, "revenue": float(total)})

    # Top companies by revenue
    top_companies = db.session.query(
        LicPayment.company_id,
        func.sum(LicPayment.amount).label("total"),
    ).filter(
        LicPayment.status == "confirmed",
    ).group_by(LicPayment.company_id).order_by(
        func.sum(LicPayment.amount).desc()
    ).limit(10).all()

    top_list = []
    for row in top_companies:
        company = db.session.get(LicCompany, row.company_id)
        top_list.append({
            "company_id": row.company_id,
            "company_name": company.name if company else None,
            "total_revenue": float(row.total),
        })

    return {
        "success": True,
        "monthly": monthly,
        "top_companies": top_list,
    }


def module_adoption_stats():
    """Which modules are most/least adopted across all companies."""
    from database import db
    from security.models import CompanyModule, ModuleCatalog

    all_modules = ModuleCatalog.query.filter_by(is_active=True).all()
    total_companies = db.session.query(CompanyModule.company_id).distinct().count() or 1

    stats = []
    for m in all_modules:
        enabled_count = CompanyModule.query.filter_by(
            module_code=m.code, enabled=True
        ).count()
        adoption_pct = round((enabled_count / total_companies) * 100, 1)
        stats.append({
            "module_code": m.code,
            "module_name": m.name,
            "enabled_count": enabled_count,
            "total_companies": total_companies,
            "adoption_pct": adoption_pct,
        })

    stats.sort(key=lambda x: x["adoption_pct"], reverse=True)
    return {"success": True, "modules": stats, "total_companies": total_companies}


def subscription_status_summary():
    """Breakdown of subscription statuses across all companies."""
    from database import db
    from licensing.models import LicSubscription, LicCompany
    from sqlalchemy import func

    rows = db.session.query(
        LicSubscription.status,
        func.count(LicSubscription.id).label("count"),
    ).group_by(LicSubscription.status).all()

    statuses = {row.status: row.count for row in rows}

    # Companies without any subscription
    company_ids_with_sub = db.session.query(LicSubscription.company_id).distinct().all()
    company_ids_with_sub = {r[0] for r in company_ids_with_sub}
    all_company_ids = {c.id for c in LicCompany.query.all()}
    no_sub = len(all_company_ids - company_ids_with_sub)

    return {
        "success": True,
        "statuses": statuses,
        "no_subscription": no_sub,
        "total_companies": len(all_company_ids),
    }
