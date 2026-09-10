"""Regression coverage for the Master password/MFA throttling boundary."""

import secrets
import uuid
from datetime import datetime

import pyotp
from werkzeug.security import generate_password_hash


def test_correct_password_waiting_for_mfa_is_not_a_login_failure(app, client):
    from database import db
    from licensing.models import LicMasterUser
    from licensing import auth as master_auth
    from security.models import MasterSession, MasterTwoFactor

    email = f"mfa-throttle-{uuid.uuid4().hex[:10]}@example.test"
    password = secrets.token_urlsafe(24)
    secret = pyotp.random_base32()

    with app.app_context():
        user = LicMasterUser(
            email=email,
            password_hash=generate_password_hash(password),
            full_name="MFA Throttle Regression",
            role="super_admin",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(MasterTwoFactor(
            master_user_id=user.id,
            secret=secret,
            enabled_at=datetime.utcnow(),
            verified_at=datetime.utcnow(),
        ))
        db.session.commit()
        user_id = user.id

    key = None
    try:
        response = client.post("/admin/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.get_json()["requires_2fa"] is True

        key = f"127.0.0.1:{email}"
        assert key not in master_auth._LOGIN_FAILURES

        # A wrong OTP must not mutate the password-failure counter into a lock.
        bad = client.post("/admin/security/2fa/verify", json={"code": "000000"})
        assert bad.status_code in (400, 401, 429)
        assert key not in master_auth._LOGIN_FAILURES
    finally:
        with app.app_context():
            db.session.query(MasterSession).filter(MasterSession.master_user_id == user_id).delete(
                synchronize_session=False
            )
            db.session.query(MasterTwoFactor).filter(MasterTwoFactor.master_user_id == user_id).delete(
                synchronize_session=False
            )
            db.session.delete(db.session.get(LicMasterUser, user_id))
            db.session.commit()
