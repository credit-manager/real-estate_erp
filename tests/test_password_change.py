# -*- coding: utf-8 -*-
"""Regression tests for the forced password-change flow.

Covers the first-login loop where a user with must_change_password=True
must be able to reach the password-change endpoint (previously blocked
by enforce_password_change with 403).
"""
import uuid

from app import _is_password_change_request


def test_password_change_paths_exempt():
    assert _is_password_change_request("/change-password") is True
    assert _is_password_change_request("/api/users/profile/password") is True
    assert _is_password_change_request("/api/change-password") is True
    assert _is_password_change_request("/api/dashboard/stats") is False
    assert _is_password_change_request("/dashboard") is False
    assert _is_password_change_request("") is False


def test_forced_change_flow(client, app):
    from database import db
    from models import User
    from werkzeug.security import generate_password_hash

    username = f"pwchange_{uuid.uuid4().hex[:8]}"
    old_pw = "Oldpass123"
    new_pw = "Newpass456"
    with app.app_context():
        user = User(
            username=username,
            email=f"{username}@example.test",
            full_name="PW Change",
            role="employee",
            password_hash=generate_password_hash(old_pw),
            is_active=True,
            must_change_password=True,
        )
        db.session.add(user)
        db.session.commit()
        uid = user.id
    try:
        r = client.post("/login", json={"username": username, "password": old_pw})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["user"]["must_change_password"] is True

        # weak password rejected
        r = client.put(
            "/api/users/profile/password",
            json={"current_password": old_pw, "new_password": "short"},
        )
        assert r.status_code == 400, r.get_json()

        # wrong current password rejected
        r = client.put(
            "/api/users/profile/password",
            json={"current_password": "Wrongpass1", "new_password": new_pw},
        )
        assert r.status_code == 400, r.get_json()

        # correct change works and clears the flag
        r = client.put(
            "/api/users/profile/password",
            json={"current_password": old_pw, "new_password": new_pw},
        )
        assert r.status_code == 200, r.get_json()

        # login with the new password, flag cleared
        r = client.post("/login", json={"username": username, "password": new_pw})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["user"]["must_change_password"] is False
    finally:
        with app.app_context():
            from models import AuditLog, LicenseActivity

            db.session.query(AuditLog).filter(
                AuditLog.user_id == uid
            ).delete(synchronize_session=False)
            try:
                db.session.query(LicenseActivity).filter(
                    LicenseActivity.user_id == uid
                ).delete(synchronize_session=False)
            except Exception:
                db.session.rollback()
            u = db.session.get(User, uid)
            if u is not None:
                db.session.delete(u)
                db.session.commit()
