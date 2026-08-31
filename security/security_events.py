# -*- coding: utf-8 -*-
"""Security events, login monitoring, and emergency controls (Phase 6).

Records security-relevant events (login success/failure, lockouts,
session revocations, emergency kills) and provides emergency controls
for the platform administrator.
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def record_event(event_type, master_user_id=None, master_user_email=None,
                 ip=None, user_agent=None, details=None, severity="info"):
    """Record a security event."""
    from database import db
    from security.models import SecurityEvent

    try:
        db.session.add(SecurityEvent(
            event_type=event_type,
            master_user_id=master_user_id,
            master_user_email=master_user_email,
            ip=ip, user_agent=user_agent,
            details=details, severity=severity,
        ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error("Failed to record security event %s: %s", event_type, e)


def get_events(event_type=None, severity=None, limit=100):
    """List security events with optional filters."""
    from database import db
    from security.models import SecurityEvent

    query = SecurityEvent.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    if severity:
        query = query.filter_by(severity=severity)
    events = query.order_by(SecurityEvent.id.desc()).limit(limit).all()
    return {"success": True, "events": [e.to_dict() for e in events]}


def get_login_history(master_user_id=None, limit=50):
    """Get login attempt history (success + failure)."""
    from database import db
    from security.models import SecurityEvent

    query = SecurityEvent.query.filter(
        SecurityEvent.event_type.in_(["login_success", "login_failure", "login_locked"])
    )
    if master_user_id:
        query = query.filter_by(master_user_id=master_user_id)
    events = query.order_by(SecurityEvent.id.desc()).limit(limit).all()
    return {"success": True, "events": [e.to_dict() for e in events]}


def get_security_summary():
    """Get security summary for the dashboard."""
    from database import db
    from security.models import SecurityEvent, MasterSession
    from sqlalchemy import func

    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    login_failures_24h = SecurityEvent.query.filter(
        SecurityEvent.event_type == "login_failure",
        SecurityEvent.created_at >= last_24h,
    ).count()

    login_success_24h = SecurityEvent.query.filter(
        SecurityEvent.event_type == "login_success",
        SecurityEvent.created_at >= last_24h,
    ).count()

    critical_events_7d = SecurityEvent.query.filter(
        SecurityEvent.severity == "critical",
        SecurityEvent.created_at >= last_7d,
    ).count()

    active_sessions = MasterSession.query.filter_by(revoked=False).count()

    return {
        "success": True,
        "login_failures_24h": login_failures_24h,
        "login_success_24h": login_success_24h,
        "critical_events_7d": critical_events_7d,
        "active_sessions": active_sessions,
    }


def kill_all_sessions(exclude_user_id=None):
    """Emergency: revoke ALL active master sessions."""
    from database import db
    from security.models import MasterSession

    query = MasterSession.query.filter_by(revoked=False)
    if exclude_user_id:
        query = query.filter(MasterSession.master_user_id != exclude_user_id)

    count = query.count()
    query.update({"revoked": True})
    db.session.commit()

    record_event("emergency_kill_all", details={"revoked_count": count}, severity="critical")
    log.warning("EMERGENCY: Revoked %d master sessions", count)
    return {"success": True, "revoked": count, "message": f"تم إنهاء {count} جلسة"}


def kill_user_sessions(master_user_id, actor_email=None, actor_id=None, ip=None):
    """Revoke all sessions for a specific master user."""
    from database import db
    from security.models import MasterSession
    from security.audit import record as audit_record

    query = MasterSession.query.filter_by(master_user_id=master_user_id, revoked=False)
    count = query.count()
    query.update({"revoked": True})
    db.session.commit()

    audit_record(action="SESSIONS_KILLED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="session",
                 ip=ip, old_value=str(count), new_value="revoked", result="SUCCESS")
    record_event("session_revoked", master_user_id=master_user_id,
                 details={"revoked_count": count}, severity="warning")
    log.info("Killed %d sessions for user %d", count, master_user_id)
    return {"success": True, "revoked": count, "message": f"تم إنهاء {count} جلسة"}


def lock_account(master_user_id, actor_email=None, actor_id=None, ip=None):
    """Emergency: deactivate a master user account."""
    from database import db
    from licensing.models import LicMasterUser
    from security.audit import record as audit_record

    user = db.session.get(LicMasterUser, master_user_id)
    if not user:
        return {"success": False, "message": "المستخدم غير موجود"}

    old_status = user.is_active
    user.is_active = False
    db.session.commit()

    # Kill all their sessions
    kill_user_sessions(master_user_id, actor_email=actor_id, ip=ip)

    audit_record(action="ACCOUNT_LOCKED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="master_user",
                 resource_id=master_user_id, ip=ip,
                 old_value=str(old_status), new_value="locked", result="SUCCESS")
    record_event("account_locked", master_user_id=master_user_id,
                 master_user_email=user.email, severity="critical")
    log.warning("Locked account %d (%s)", master_user_id, user.email)
    return {"success": True, "message": f"تم قفل حساب {user.email}"}


def unlock_account(master_user_id, actor_email=None, actor_id=None, ip=None):
    """Unlock a locked master user account."""
    from database import db
    from licensing.models import LicMasterUser
    from security.audit import record as audit_record

    user = db.session.get(LicMasterUser, master_user_id)
    if not user:
        return {"success": False, "message": "المستخدم غير موجود"}

    old_status = user.is_active
    user.is_active = True
    db.session.commit()

    audit_record(action="ACCOUNT_UNLOCKED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="master_user",
                 resource_id=master_user_id, ip=ip,
                 old_value=str(old_status), new_value="unlocked", result="SUCCESS")
    record_event("account_unlocked", master_user_id=master_user_id,
                 master_user_email=user.email, severity="warning")
    log.info("Unlocked account %d (%s)", master_user_id, user.email)
    return {"success": True, "message": f"تم فتح حساب {user.email}"}
