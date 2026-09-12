# -*- coding: utf-8 -*-
"""TOTP 2FA for the Master Control Center.

The control-center MFA verifier is deliberately fail-closed and rate limited.
A password-verified master user still has only a pending-MFA session until OTP
or a recovery code succeeds.
"""
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
from datetime import datetime

import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
import config

log = logging.getLogger(__name__)
ISSUER = "ERP Control Center"
MFA_MAX_ATTEMPTS = config.MAX_LOGIN_ATTEMPTS
MFA_LOCK_SECONDS = 300
_MFA_FAILURES = {}
_mfa_lock = threading.Lock()
_REDIS_CLIENT = None
_REDIS_UNAVAILABLE = False


def generate_secret():
    return pyotp.random_base32()


def provisioning_uri(user_email, secret):
    return pyotp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=ISSUER)


def _redis_mfa_store():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE
    if getattr(sys, "frozen", False):
        return None  # Frozen desktop is single-user: in-memory store is correct.
    env = str(os.environ.get("DYNAMICPRO_ENV", "")).strip().lower()
    if env not in {"production", "prod"}:
        return None
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _REDIS_UNAVAILABLE:
        raise RuntimeError("Production MFA protection cannot connect to Redis.")
    uri = os.environ.get("REDIS_URL") or os.environ.get("RATELIMIT_STORAGE_URI")
    if not uri or not uri.lower().startswith(("redis://", "rediss://")):
        raise RuntimeError("Production MFA protection requires Redis storage.")
    try:
        import redis
        _REDIS_CLIENT = redis.Redis.from_url(
            uri,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _REDIS_CLIENT.ping()
        return _REDIS_CLIENT
    except Exception as exc:
        _REDIS_CLIENT = None
        _REDIS_UNAVAILABLE = True
        raise RuntimeError("Production MFA protection cannot connect to Redis.") from exc


def _mfa_key(master_user_id):
    digest = hashlib.sha256(str(master_user_id).encode("utf-8")).hexdigest()
    return f"dynamicpro:mfa:verify:{digest}"


def _mfa_attempt_allowed(master_user_id):
    store = _redis_mfa_store()
    if store is not None:
        key = _mfa_key(master_user_id)
        remaining = store.ttl(f"{key}:lock")
        if remaining > 0:
            return False
        return True
    rec = _MFA_FAILURES.get(master_user_id)
    if not rec:
        return True
    lock_until = rec.get("lock_until", 0)
    if lock_until > time.time():
        return False
    with _mfa_lock:
        _MFA_FAILURES.pop(master_user_id, None)
    return True


def _register_mfa_failure(master_user_id):
    store = _redis_mfa_store()
    if store is not None:
        key = _mfa_key(master_user_id)
        count = store.incr(f"{key}:count")
        if count == 1:
            store.expire(f"{key}:count", MFA_LOCK_SECONDS)
        if count >= MFA_MAX_ATTEMPTS:
            store.set(f"{key}:lock", "1", ex=MFA_LOCK_SECONDS)
        return
    with _mfa_lock:
        rec = _MFA_FAILURES.setdefault(master_user_id, {"count": 0, "lock_until": 0})
        rec["count"] += 1
        if rec["count"] >= MFA_MAX_ATTEMPTS:
            rec["lock_until"] = time.time() + MFA_LOCK_SECONDS


def _reset_mfa_failures(master_user_id):
    store = _redis_mfa_store()
    if store is not None:
        key = _mfa_key(master_user_id)
        store.delete(f"{key}:count", f"{key}:lock")
        return
    with _mfa_lock:
        _MFA_FAILURES.pop(master_user_id, None)


def enroll(master_user_id, user_email):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if mfa is None:
        mfa = MasterTwoFactor(master_user_id=master_user_id, secret=generate_secret())
        db.session.add(mfa)
    else:
        mfa.secret = generate_secret()
        mfa.enabled_at = None
        mfa.verified_at = None
        mfa.recovery_codes_hash = None
    db.session.commit()
    _reset_mfa_failures(master_user_id)
    return mfa.secret, provisioning_uri(user_email, mfa.secret)


def verify_code(master_user_id, code):
    """Verify a TOTP code and complete a pending password+MFA master login."""
    from security.models import MasterTwoFactor
    if not _mfa_attempt_allowed(master_user_id):
        return False

    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa or not mfa.secret:
        _register_mfa_failure(master_user_id)
        return False
    code = (code or "").strip()
    if not code.isdigit() or len(code) != 6:
        _register_mfa_failure(master_user_id)
        return False
    if not pyotp.TOTP(mfa.secret).verify(code, valid_window=1):
        _register_mfa_failure(master_user_id)
        return False

    _reset_mfa_failures(master_user_id)
    now = datetime.utcnow()
    if not mfa.enabled_at:
        mfa.enabled_at = now
        mfa.verified_at = now
    mfa.last_used_at = now
    db.session.commit()
    try:
        from licensing.auth import complete_pending_master_mfa, is_pending_mfa_session
        if is_pending_mfa_session():
            return complete_pending_master_mfa(master_user_id)
    except Exception:
        log.exception("Failed to complete pending master MFA session")
        return False
    return True


def is_enabled(master_user_id):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    return bool(mfa and mfa.enabled_at)


def disable(master_user_id):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if mfa:
        db.session.delete(mfa)
        db.session.commit()
    _reset_mfa_failures(master_user_id)
    return True


def generate_recovery_codes(master_user_id, count=8):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa:
        return []
    count = max(4, min(int(count), 12))
    codes = []
    hashes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(raw)
        hashes.append(generate_password_hash(raw))
    mfa.recovery_codes_hash = json.dumps(hashes)
    db.session.commit()
    _reset_mfa_failures(master_user_id)
    return codes


def verify_recovery_code(master_user_id, code):
    from security.models import MasterTwoFactor
    if not _mfa_attempt_allowed(master_user_id):
        return False
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa or not mfa.recovery_codes_hash:
        _register_mfa_failure(master_user_id)
        return False
    try:
        hashes = json.loads(mfa.recovery_codes_hash)
    except (ValueError, TypeError):
        _register_mfa_failure(master_user_id)
        return False
    if not isinstance(hashes, list):
        _register_mfa_failure(master_user_id)
        return False

    remaining = []
    matched = False
    candidate = (code or "").strip().upper()
    for stored in hashes:
        if not matched and isinstance(stored, str) and check_password_hash(stored, candidate):
            matched = True
            continue
        remaining.append(stored)
    if not matched:
        _register_mfa_failure(master_user_id)
        return False

    _reset_mfa_failures(master_user_id)
    mfa.recovery_codes_hash = json.dumps(remaining)
    db.session.commit()
    try:
        from licensing.auth import complete_pending_master_mfa, is_pending_mfa_session
        if is_pending_mfa_session():
            return complete_pending_master_mfa(master_user_id)
    except Exception:
        log.exception("Failed to complete pending master MFA recovery session")
        return False
    return True


def require_two_factor(master_user_id):
    from security.rbac import user_permissions, _all_codes
    if user_permissions(master_user_id) >= set(_all_codes()):
        return is_enabled(master_user_id)
    return True
