# -*- coding: utf-8 -*-
"""JWT token handling for the Master Control Center (Phase 1).

Provides short-lived **access** tokens and longer-lived **refresh** tokens,
signed with PyJWT using HS256 and the instance secret.  Refresh tokens are
bound to a persisted ``MasterSession`` row (by ``jti``) so they can be revoked
individually (logout / emergency kill-switch) rather than relying only on
expiry.
"""
import logging
import time
import uuid
from datetime import datetime, timedelta

import jwt

from config import SECRET_KEY

log = logging.getLogger(__name__)

ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=7)

ALGORITHM = "HS256"
ISSUER = "dynamicpro-control-center"


def _secret():
    # Fall back to a per-install generated key if SECRET_KEY is not set, so the
    # module stays usable in tests/scratch. Production must set SECRET_KEY.
    if SECRET_KEY:
        return SECRET_KEY
    return "dev-only-insecure-secret-do-not-use"


def issue_token_pair(master_user_id, email, name, permissions, jti=None, now=None):
    """Issue an access + refresh token pair and the refresh token's jti.

    Returns (access_token, refresh_token, jti).
    """
    now = now or datetime.utcnow()
    jti = jti or uuid.uuid4().hex

    def _payload(token_type, ttl, extra_claims=None):
        payload = {
            "iss": ISSUER,
            "sub": str(master_user_id),
            "email": email,
            "name": name,
            "typ": token_type,
            "iat": int(time.mktime(now.timetuple())),
            "exp": int(time.mktime((now + ttl).timetuple())),
            "jti": jti,
        }
        if extra_claims:
            payload.update(extra_claims)
        return payload

    access = jwt.encode(
        _payload("access", ACCESS_TTL, {"perms": sorted(permissions)}),
        _secret(),
        algorithm=ALGORITHM,
    )
    refresh = jwt.encode(_payload("refresh", REFRESH_TTL), _secret(), algorithm=ALGORITHM)
    return access, refresh, jti


def decode_token(token, expected_type=None):
    """Decode + validate a token. Returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM], issuer=ISSUER)
    except jwt.ExpiredSignatureError:
        return None
    except (jwt.InvalidTokenError, Exception) as e:
        log.debug("Invalid token: %s", e)
        return None
    if expected_type and payload.get("typ") != expected_type:
        return None
    return payload


def refresh_access_token(refresh_token):
    """Exchange a valid refresh token for a new access token.

    Returns (access_token, payload) or (None, None).
    """
    from security.models import MasterSession

    payload = decode_token(refresh_token, expected_type="refresh")
    if not payload:
        return None, None

    jti = payload.get("jti")
    sess = MasterSession.query.filter_by(jti=jti, revoked=False).first()
    if not sess:
        return None, None
    if sess.expires_at and sess.expires_at < datetime.utcnow():
        return None, None

    master_user_id = int(payload["sub"])
    from licensing.models import LicMasterUser
    user = db_session_get(LicMasterUser, master_user_id)
    if not user or not user.is_active:
        return None, None

    from security.rbac import user_permissions
    perms = user_permissions(user.id)
    access, _, _ = issue_token_pair(
        user.id, user.email, user.full_name or user.email, perms, jti=jti
    )
    sess.last_seen = datetime.utcnow()
    commit_db()
    return access, {"sub": payload["sub"], "email": user.email}


# Thin indirection so this module does not hard-depend on the app's session
# object beyond an import; avoids circular import at module load time.
def db_session_get(model, pk):
    from database import db
    return db.session.get(model, pk)


def commit_db():
    from database import db
    db.session.commit()
