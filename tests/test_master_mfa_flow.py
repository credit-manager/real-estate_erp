# -*- coding: utf-8 -*-
"""Regression tests for the mandatory Master Control Center MFA flow."""
from datetime import datetime
import secrets
import uuid

import pyotp
from werkzeug.security import generate_password_hash


def test_master_password_alone_never_creates_authenticated_session(app, client):
    from database import db
    from licensing.models import LicMasterUser
    from security.models import MasterSession, MasterTwoFactor

    email = f"mfa_{uuid.uuid4().hex[:10]}@example.test"
    password = secrets.token_urlsafe(24)
    secret = pyotp.random_base32()
    with app.app_context():
        user = LicMasterUser(
            email=email,
            password_hash=generate_password_hash(password),
            full_name="MFA Regression",
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

    try:
        response = client.post("/admin/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.get_json()["requires_2fa"] is True

        dashboard = client.get("/admin/dashboard")
        assert dashboard.status_code == 401
        assert client.get("/admin/security/security/summary").status_code == 401

        code = pyotp.TOTP(secret).now()
        response = client.post("/admin/security/2fa/verify", json={"code": code})
        assert response.status_code == 200
        assert response.get_json()["success"] is True

        with app.app_context():
            active = MasterSession.query.filter_by(master_user_id=user_id, revoked=False).all()
            assert len(active) == 1
    finally:
        with app.app_context():
            db.session.query(MasterSession).filter(MasterSession.master_user_id == user_id).delete(synchronize_session=False)
            db.session.query(MasterTwoFactor).filter(MasterTwoFactor.master_user_id == user_id).delete(synchronize_session=False)
            db.session.delete(db.session.get(LicMasterUser, user_id))
            db.session.commit()
