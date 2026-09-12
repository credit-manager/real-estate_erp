# -*- coding: utf-8 -*-
"""JWT token handling for the Master Control Center.

Provides short-lived access tokens and longer-lived refresh tokens, signed
with HS256 and the instance secret. Refresh tokens are bound to a persisted
``MasterSession`` row so they can be revoked individually.
"""
import calendar
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from config import SECRET_KEY

log = logging.getLogger(__name__)
ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=7)
ALGORITHM = "HS256"
ISSUER = "dynamicpro-control-center"


def _secret():
    """Return the JWT signing key. Production must use the configured secret."""
    if SECRET_KEY:
        return SECRET_KEY
    if os.environ.get("DYNAMICPRO_ENV", "").strip().lower() in {"prod", "production"}:
        raise RuntimeError("JWT signing secret is required in production.")

    key_file = os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"),
        "DynamicPro", ".jwt_secret"
    )
    try:
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        if os.path.isfile(key_file):
            with open(key_file, "r", encoding="utf-8") as fh:
                key = fh.read().strip()
            if len(key) >= 32:
                return key
        key = secrets.token_hex(32)
        with open(key_file, "w", encoding="utf-8") as fh:
            fh.write(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return key
    except OSError as exc:
        raise RuntimeError("Unable to persist the local JWT signing secret.") from exc


def _utc_epoch(value: datetime) -> int:
    """Convert a naive-or-aware datetime to a real UTC epoch without local TZ drift."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return calendar.timegm(value.utctimetuple())


def issue_token_pair(master_user_id, email, name, permissions, jti=None, now=None):
    """Issue an access + refresh token pair and return both with the session JTI."""
    now = now or datetime.now(timezone.utc)
    jti = jti or uuid.uuid4().hex
    issued_at = _utc_epoch(now)

    access_payload = {
        "iss": ISSUER,
        "sub": str(master_user_id),
        "email": email,
        "name": name,
        "typ": "access",
        "iat": issued_at,
        "exp": _utc_epoch(now + ACCESS_TTL),
        "jti": jti,
        "perms": sorted(permissions),
    }
    refresh_payload = {
        "iss": ISSUER,
        "sub": str(master_user_id),
        "email": email,
        "name": name,
        "typ": "refresh",
        "iat": issued_at,
        "exp": _utc_epoch(now + REFRESH_TTL),
        "jti": jti,
    }
    access = jwt.encode(access_payload, _secret(), algorithm=ALGORITHM)
    refresh = jwt.encode(refresh_payload, _secret(), algorithm=ALGORITHM)
    return access, refresh, jti


def decode_token(token, expected_type=None):
    """Decode and validate a token. Return payload or None when invalid/expired."""
    if not isinstance(token, str) or not token.strip():
        return None
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["iss", "sub", "iat", "exp", "jti", "typ"]},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as exc:
        log.debug("Invalid token: %s", exc)
        return None
    if expected_type and payload.get("typ") != expected_type:
        return None
    return payload


def refresh_access_token(refresh_token):
    """Exchange a valid, revocable refresh token for a fresh access token.

    Refresh tokens intentionally remain valid until their 7-day expiry or the
    backing ``MasterSession`` is revoked; callers receive only a new access
    token, so there is no accidentally discarded refresh token.
    """
    from security.models import MasterSession

    payload = decode_token(refresh_token, expected_type="refresh")
    if not payload:
        return None, None

    jti = payload.get("jti")
    sess = MasterSession.query.filter_by(jti=jti, revoked=False).first()
    if not sess or (sess.expires_at and sess.expires_at < datetime.utcnow()):
        return None, None

    try:
        master_user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None, None

    from licensing.models import LicMasterUser
    user = db_session_get(LicMasterUser, master_user_id)
    if not user or not user.is_active:
        return None, None

    from security.rbac import user_permissions
    access, _, _ = issue_token_pair(
        user.id,
        user.email,
        user.full_name or user.email,
        user_permissions(user.id),
        jti=jti,
    )
    # Persist session activity without rotating the refresh credential.
    sess.last_seen = datetime.utcnow()
    commit_db()
    return access, {"sub": str(user.id), "email": user.email, "jti": jti}


# Thin indirection so this module does not hard-depend on the Flask session
# object beyond an import; avoids circular import at module load time.
def db_session_get(model, pk):
    from database import db
    return db.session.get(model, pk)


def commit_db():
    from database import db
    db.session.commit()
