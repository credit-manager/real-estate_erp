from flask import session
from database import db
from models import AuditLog


def log_action(action, entity, entity_id=None, description=""):
    try:
        db.session.add(AuditLog(
            user_id=session.get("user_id"),
            username=session.get("username") or session.get("full_name"),
            action=action,
            entity=entity,
            entity_id=entity_id,
            description=(description or "")[:300],
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
