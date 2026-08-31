# -*- coding: utf-8 -*-
"""TOTP 2FA for the Master Control Center (Phase 1).

Uses pyotp (RFC 6238 TOTP) against a per-user secret stored in the
``master_two_factor`` table.  Secrets are never returned after enrollment;
only the otpauth:// provisioning URI (for the authenticator app QR) and the
raw secret are shown once at enrollment time.

The spec mandates: **no Super Admin without 2FA** — enforced by
``require_two_factor()`` for roles that carry elevated privileges.
"""
import hashlib
import hmac
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
    """Create a base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(user_email, secret):
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=user_email, issuer_name=ISSUER)


def enroll(master_user_id, user_email):
    """Create and return a fresh TOTP secret + provisioning URI (shown once)."""
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
    """Validate a 6-digit TOTP code for the given master user.

    Enables the user's 2FA upon the first successful verification.
    """
    from security.models import MasterTwoFactor

    mfa = MasterTwoFactor.query.filter_by(master_user_id=master_user_id).first()
    if not mfa or not mfa.secret:
        return False
    totp = pyotp.TOTP(mfa.secret)
    if totp.verify(code, valid_window=1):
        if not mfa.enabled_at:
            mfa.enabled_at = datetime.utcnow()
            mfa.verified_at = datetime.utcnow()
        mfa.last_used_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


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
    now = []
    for h in hashes:
        if check_password_hash(h, code.strip().upper()):
            # consume the code: remove it and keep remaining
            continue
        now.append(h)
    if len(now) != len(hashes):
        mfa.recovery_codes_hash = json.dumps(now)
        db.session.commit()
        return True
    return False


def require_two_factor(master_user_id):
    """Require that 2FA is enabled for a super_admin (or any 2FA-mandated user).

    Returns True if enforcement should apply AND is satisfied.
    """
    from security.rbac import user_permissions, _all_codes
    # A user holding every permission is a super admin — 2FA is mandatory.
    if user_permissions(master_user_id) >= set(_all_codes()):
        return is_enabled(master_user_id)
    return True
