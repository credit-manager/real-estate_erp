# -*- coding: utf-8 -*-
"""Secure JWT access/refresh token handling for the control center."""
import logging
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
    if not SECRET_KEY:
        raise RuntimeError("JWT signing key is not configured")
    return SECRET_KEY


def _utc_now(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def issue_token_pair(master_user_id, email, name, permissions, jti=None, now=None):
    """Issue an access + refresh pair and the persisted refresh-token identifier."""
    now = _utc_now(now)
    jti = jti or uuid.uuid4().hex

    def _payload(token_type, ttl, extra_claims=None):
        payload = {
            "iss": ISSUER,
            "sub": str(master_user_id),
            "email": email,
            "name": name,
            "typ": token_type,
            "iat": now,
            "exp": now + ttl,
            "jti": jti,
        }
        if extra_claims:
            payload.update(extra_claims)
        return payload

    access = jwt.encode(
        _payload("access", ACCESS_TTL, {"perms": sorted(set(permissions or []))}),
        _secret(),
        algorithm=ALGORITHM,
    )
    refresh = jwt.encode(
        _payload("refresh", REFRESH_TTL),
        _secret(),
        algorithm=ALGORITHM,
    )
    return access, refresh, jti


def decode_token(token, expected_type=None):
    """Decode and validate a JWT. Invalid tokens return None without hiding programming errors."""
    if not token or not isinstance(token, str):
        return None
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["iss", "sub", "typ", "iat", "exp", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as exc:
        log.debug("Invalid token: %s", exc)
        return None
    if expected_type and payload.get("typ") != expected_type:
        return None
    if payload.get("typ") not in {"access", "refresh"}:
        return None
    return payload


def refresh_access_token(refresh_token):
    """Exchange a valid refresh token for a new access token.

    The persisted session remains the revocation authority. The refresh token
    identifier is deliberately preserved for backwards-compatible session
    lookup; a future rotation endpoint can revoke-and-reissue the identifier.
    """
    from security.models import MasterSession

    payload = decode_token(refresh_token, expected_type="refresh")
    if not payload:
        return None, None

    jti = payload.get("jti")
    if not jti:
        return None, None
    sess = MasterSession.query.filter_by(jti=jti, revoked=False).first()
    if not sess:
        return None, None

    now = datetime.now(timezone.utc)
    if sess.expires_at:
        expires_at = _utc_now(sess.expires_at)
        if expires_at <= now:
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

    permissions = user_permissions(user.id)
    access, _, _ = issue_token_pair(
        user.id,
        user.email,
        user.full_name or user.email,
        permissions,
        jti=jti,
        now=now,
    )
    sess.last_seen = now.replace(tzinfo=None)
    commit_db()
    return access, {"sub": payload["sub"], "email": user.email}


def db_session_get(model, pk):
    from database import db

    return db.session.get(model, pk)


def commit_db():
    from database import db

    db.session.commit()
