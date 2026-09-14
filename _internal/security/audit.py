# -*- coding: utf-8 -*-
"""Master-side audit logger (Phase 1 groundwork; full UI in Phase 6).

Every sensitive operation inside the Control Center should record a row here:
who, what, when, company, ip, session, old/new value, and result.  This is the
single durable audit trail, separate from the company-level LicAudit tables.
"""
import logging
from typing import Any, Optional

from database import db

log = logging.getLogger(__name__)


def record(
    action: str,
    master_user_id: Optional[int] = None,
    master_user_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    company_id: Optional[int] = None,
    ip: Optional[str] = None,
    session_jti: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    result: str = "SUCCESS",
) -> None:
    """Append a row to master_audit_logs (does not raise on failure)."""
    from security.models import MasterAuditLog

    try:
        db.session.add(
            MasterAuditLog(
                action=action,
                master_user_id=master_user_id,
                master_user_email=master_user_email,
                resource_type=resource_type,
                resource_id=resource_id,
                company_id=company_id,
                ip=ip,
                session_jti=session_jti,
                old_value=str(old_value)[:1000] if old_value is not None else None,
                new_value=str(new_value)[:1000] if new_value is not None else None,
                result=result,
            )
        )
        db.session.commit()
    except Exception as e:  # audit must never take down the request
        db.session.rollback()
        log.error("Audit record failed (%s): %s", action, e)
