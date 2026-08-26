"""Notification center + Firebase Cloud Messaging (FCM) push helper."""
import json
import logging
from database import db

log = logging.getLogger(__name__)


def notify(user_id, title, message="", category="general", severity="info", link=None):
    """Create an in-app notification for a user and push it to their devices."""
    from models import AppNotification, DeviceToken

    if not user_id:
        return None
    rec = AppNotification(
        user_id=user_id,
        title=title,
        message=message,
        category=category,
        severity=severity,
        link=link,
    )
    db.session.add(rec)
    db.session.commit()

    tokens = [
        t.token
        for t in DeviceToken.query.filter_by(user_id=user_id).all()
        if t.token
    ]
    if tokens:
        try:
            fcm_send(tokens, title, message, category)
        except Exception as exc:  # pragma: no cover - network errors
            log.warning("FCM send failed: %s", exc)
    return rec.id


def notify_many(user_ids, title, message="", category="general", severity="info", link=None):
    """Notify many users (deduplicated)."""
    for uid in set(user_ids or []):
        try:
            notify(uid, title, message, category, severity, link)
        except Exception as exc:
            log.warning("notify(%s) failed: %s", uid, exc)


def fcm_send(tokens, title, body, category="general"):
    """Send a push via Firebase HTTP v1 API using a server key or legacy key."""
    import utils.settings as settings_module

    server_key = settings_module.get("fcm_server_key", "")
    if not server_key:
        return
    url = "https://fcm.googleapis.com/fcm/send"
    payload = {
        "registration_ids": tokens,
        "notification": {
            "title": title,
            "body": body or "",
            "sound": "default",
        },
        "data": {"category": category, "title": title, "body": body or ""},
        "priority": "high",
    }
    import requests

    resp = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": "key=" + server_key,
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        log.warning("FCM response %s: %s", resp.status_code, resp.text[:300])
