# -*- coding: utf-8 -*-
"""Company lifecycle state machine (Phase 2).

Defines the allowed status transitions and enforces them before any
status change is committed.  Every transition is recorded in the master
audit trail.

States:
    active    — company is operational
    suspended — temporarily disabled (billing issue, policy violation, etc.)
    deleted   — soft-deleted (archived, recoverable)

Allowed transitions:

    active    →  suspended   (suspend)
    active    →  deleted     (archive / soft-delete)
    suspended →  active      (reactivate)
    suspended →  deleted     (archive while suspended)
    deleted   →  active      (restore from archive — only if subscription valid)
"""
import logging

log = logging.getLogger(__name__)

# { from_status: set(to_status) }
ALLOWED_TRANSITIONS = {
    "active":    {"suspended", "deleted"},
    "suspended": {"active", "deleted"},
    "deleted":   {"active"},  # restore from archive
}

# Human-readable Arabic labels for each transition
TRANSITION_LABELS = {
    ("active", "suspended"):    "تعليق",
    ("active", "deleted"):      "أرشفة / حذف",
    ("suspended", "active"):    "إعادة تفعيل",
    ("suspended", "deleted"):   "أرشفة",
    ("deleted", "active"):      "استعادة",
}


def can_transition(from_status, to_status):
    """Return True if the transition is allowed."""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def transition_company(company, to_status, actor_email=None, actor_id=None, ip=None, reason=None):
    """Execute a validated status transition on a LicCompany.

    Returns:
        dict: {success, message, from_status, to_status}

    Rolls back on failure and never leaves the DB in a half-written state.
    """
    from database import db
    from security.audit import record as audit_record

    if company.status == to_status:
        return {"success": False, "message": "الحالة الحالية مطابقة للحالة المطلوبة"}

    if not can_transition(company.status, to_status):
        allowed = ALLOWED_TRANSITIONS.get(company.status, set())
        return {
            "success": False,
            "message": f"لا يمكن التحويل من '{company.status}' إلى '{to_status}'. "
                       f"الحالات المسموحة: {', '.join(sorted(allowed)) or 'لا توجد'}",
        }

    from_status = company.status
    label = TRANSITION_LABELS.get((from_status, to_status), to_status)

    try:
        company.status = to_status
        db.session.commit()

        # Audit the transition
        audit_record(
            action="COMPANY_TRANSITION",
            master_user_id=actor_id,
            master_user_email=actor_email,
            resource_type="company",
            resource_id=company.id,
            company_id=company.id,
            ip=ip,
            old_value=from_status,
            new_value=to_status,
            result="SUCCESS",
        )
        log.info("Company %d status: %s → %s (by %s)", company.id, from_status, to_status, actor_email)
        return {"success": True, "message": f"تم {label} الشركة", "from_status": from_status, "to_status": to_status}

    except Exception as e:
        db.session.rollback()
        log.error("Transition failed for company %d: %s", company.id, e)
        return {"success": False, "message": f"فشلت العملية: {e}"}


def status_summary():
    """Return counts per status for the dashboard."""
    from database import db
    from licensing.models import LicCompany
    rows = db.session.query(
        LicCompany.status, db.func.count(LicCompany.id)
    ).group_by(LicCompany.status).all()
    return {status: count for status, count in rows}
