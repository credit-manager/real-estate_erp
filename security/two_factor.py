# -*- coding: utf-8 -*-
"""TOTP 2FA for the Master Control Center."""
import json
import logging
import secrets
from datetime import datetime

import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

log = logging.getLogger(__name__)
ISSUER = "ERP Control Center"


def generate_secret():
    return pyotp.random_base32()


def provisioning_uri(user_email, secret):
    return pyotp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=ISSUER)


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
    return mfa.secret, provisioning_uri(user_email, mfa.secret)


def verify_code(master_user_id, code):
    """Verify a TOTP code and complete a pending password+MFA master login."""
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa or not mfa.secret:
        return False
    code = (code or "").strip()
    if not code.isdigit() or len(code) != 6:
        return False
    if not pyotp.TOTP(mfa.secret).verify(code, valid_window=1):
        return False
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
    return True


def generate_recovery_codes(master_user_id, count=8):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa:
        return []
    codes = []
    hashes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(raw)
        hashes.append(generate_password_hash(raw))
    mfa.recovery_codes_hash = json.dumps(hashes)
    db.session.commit()
    return codes


def verify_recovery_code(master_user_id, code):
    from security.models import MasterTwoFactor
    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa or not mfa.recovery_codes_hash:
        return False
    try:
        hashes = json.loads(mfa.recovery_codes_hash)
    except (ValueError, TypeError):
        return False
    remaining = []
    matched = False
    candidate = (code or "").strip().upper()
    for stored in hashes:
        if not matched and check_password_hash(stored, candidate):
            matched = True
            continue
        remaining.append(stored)
    if matched:
        mfa.recovery_codes_hash = json.dumps(remaining)
        db.session.commit()
        try:
            from licensing.auth import complete_pending_master_mfa, is_pending_mfa_session
            if is_pending_mfa_session():
                return complete_pending_master_mfa(master_user_id)
        except Exception:
            log.exception("Failed to complete pending master MFA recovery session")
            return False
    return False


def require_two_factor(master_user_id):
    from security.rbac import user_permissions, _all_codes
    if user_permissions(master_user_id) >= set(_all_codes()):
        return is_enabled(master_user_id)
    return True
