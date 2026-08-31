# -*- coding: utf-8 -*-
"""Billing lifecycle functions (Phase 4).

High-level operations for payments, revenue statistics, and payment history,
composing the existing LicPayment model with audit logging.

All functions return dict {success, message, ...} and record audit trails.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

log = logging.getLogger(__name__)


def create_payment(company_id, amount, currency="EGP", payment_method="cash",
                   reference_no="", subscription_id=None,
                   actor_email=None, actor_id=None, ip=None):
    """Record a new payment."""
    from database import db
    from licensing.models import LicCompany, LicPayment
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    if not amount or float(amount) <= 0:
        return {"success": False, "message": "المبلغ غير صالح"}

    # Auto-detect subscription if not provided
    if not subscription_id:
        sub = company.active_subscription
        subscription_id = sub.id if sub else None

    payment = LicPayment(
        company_id=company_id,
        subscription_id=subscription_id,
        amount=amount, currency=currency,
        payment_method=payment_method,
        reference_no=reference_no,
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    audit_record(action="PAYMENT_CREATED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="payment",
                 resource_id=payment.id, company_id=company_id, ip=ip,
                 new_value=f"{amount} {currency}", result="SUCCESS")
    log.info("Created payment %d: %s %s for company %d", payment.id, amount, currency, company_id)
    return {"success": True, "payment": payment.to_dict(), "message": "تم تسجيل الدفعة"}


def confirm_payment(payment_id, confirmed_by=None, actor_email=None, actor_id=None, ip=None):
    """Confirm a pending payment."""
    from database import db
    from licensing.models import LicPayment
    from datetime import datetime
    from security.audit import record as audit_record

    payment = db.session.get(LicPayment, payment_id)
    if not payment:
        return {"success": False, "message": "الدفعة غير موجودة"}

    if payment.status == "confirmed":
        return {"success": False, "message": "الدفعة مؤكدة مسبقاً"}

    old_status = payment.status
    payment.status = "confirmed"
    payment.paid_at = datetime.utcnow()
    payment.confirmed_by = confirmed_by or actor_email
    db.session.commit()

    audit_record(action="PAYMENT_CONFIRMED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="payment",
                 resource_id=payment.id, company_id=payment.company_id, ip=ip,
                 old_value=old_status, new_value="confirmed", result="SUCCESS")
    log.info("Confirmed payment %d (%s %s)", payment.id, payment.amount, payment.currency)
    return {"success": True, "payment": payment.to_dict(), "message": "تم تأكيد الدفعة"}


def refund_payment(payment_id, reason="", actor_email=None, actor_id=None, ip=None):
    """Refund a confirmed payment."""
    from database import db
    from licensing.models import LicPayment
    from security.audit import record as audit_record

    payment = db.session.get(LicPayment, payment_id)
    if not payment:
        return {"success": False, "message": "الدفعة غير موجودة"}

    if payment.status == "refunded":
        return {"success": False, "message": "الدفعة مستردة مسبقاً"}

    old_status = payment.status
    payment.status = "refunded"
    db.session.commit()

    audit_record(action="PAYMENT_REFUNDED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="payment",
                 resource_id=payment.id, company_id=payment.company_id, ip=ip,
                 old_value=old_status, new_value="refunded",
                 result="SUCCESS")
    log.info("Refunded payment %d (%s %s) reason: %s", payment.id, payment.amount, payment.currency, reason)
    return {"success": True, "payment": payment.to_dict(), "message": "تم استرداد الدفعة"}


def fail_payment(payment_id, reason="", actor_email=None, actor_id=None, ip=None):
    """Mark a payment as failed."""
    from database import db
    from licensing.models import LicPayment
    from security.audit import record as audit_record

    payment = db.session.get(LicPayment, payment_id)
    if not payment:
        return {"success": False, "message": "الدفعة غير موجودة"}

    old_status = payment.status
    payment.status = "failed"
    db.session.commit()

    audit_record(action="PAYMENT_FAILED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="payment",
                 resource_id=payment.id, company_id=payment.company_id, ip=ip,
                 old_value=old_status, new_value="failed", result="SUCCESS")
    log.info("Marked payment %d as failed: %s", payment.id, reason)
    return {"success": True, "payment": payment.to_dict(), "message": "تم تحديد الدفعة كفاشلة"}


def revenue_stats(period="monthly", months=6):
    """Calculate revenue statistics for the dashboard.

    Returns monthly revenue breakdown and totals.
    """
    from database import db
    from licensing.models import LicPayment
    from sqlalchemy import func, extract

    today = date.today()
    results = []

    for i in range(months - 1, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=i * 30)
        year = month_date.year
        month = month_date.month

        confirmed = db.session.query(func.sum(LicPayment.amount)).filter(
            LicPayment.status == "confirmed",
            extract("year", LicPayment.paid_at) == year,
            extract("month", LicPayment.paid_at) == month,
        ).scalar() or Decimal(0)

        pending = db.session.query(func.sum(LicPayment.amount)).filter(
            LicPayment.status == "pending",
            LicPayment.created_at >= date(year, month, 1),
            LicPayment.created_at < date(year + (month // 12), (month % 12) + 1, 1),
        ).scalar() or Decimal(0)

        results.append({
            "year": year,
            "month": month,
            "confirmed": float(confirmed),
            "pending": float(pending),
            "total": float(confirmed + pending),
        })

    total_confirmed = sum(r["confirmed"] for r in results)
    total_pending = sum(r["pending"] for r in results)

    return {
        "success": True,
        "monthly": results,
        "total_confirmed": total_confirmed,
        "total_pending": total_pending,
        "total": total_confirmed + total_pending,
    }


def payment_history(company_id=None, limit=50):
    """Get payment history, optionally filtered by company."""
    from database import db
    from licensing.models import LicPayment, LicCompany

    query = LicPayment.query
    if company_id:
        query = query.filter_by(company_id=company_id)

    payments = query.order_by(LicPayment.id.desc()).limit(limit).all()

    result = []
    for p in payments:
        d = p.to_dict()
        company = db.session.get(LicCompany, p.company_id)
        d["company_name"] = company.name if company else None
        result.append(d)

    return {"success": True, "payments": result}


def payment_summary_by_company():
    """Get payment totals grouped by company."""
    from database import db
    from licensing.models import LicPayment, LicCompany
    from sqlalchemy import func

    rows = db.session.query(
        LicPayment.company_id,
        func.count(LicPayment.id).label("count"),
        func.sum(LicPayment.amount).label("total_amount"),
        func.sum(db.case((LicPayment.status == "confirmed", LicPayment.amount), else_=0)).label("confirmed_amount"),
    ).group_by(LicPayment.company_id).all()

    result = []
    for row in rows:
        company = db.session.get(LicCompany, row.company_id)
        result.append({
            "company_id": row.company_id,
            "company_name": company.name if company else None,
            "payment_count": row.count,
            "total_amount": float(row.total_amount or 0),
            "confirmed_amount": float(row.confirmed_amount or 0),
        })

    return {"success": True, "summary": result}
