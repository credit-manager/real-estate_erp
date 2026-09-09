def test_valid_master_password_with_mfa_is_not_counted_as_login_failure(app, client):
    from datetime import datetime
    import secrets
    import uuid

    import pyotp
    from werkzeug.security import generate_password_hash

    from database import db
    from licensing.models import LicMasterUser
    from licensing.auth import _LOGIN_FAILURES
    from security.models import MasterTwoFactor

    email = f"mfa-throttle_{uuid.uuid4().hex[:10]}@example.test"
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

    key = f"127.0.0.1:{email}"
    try:
        response = client.post("/admin/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.get_json()["requires_2fa"] is True
        assert key not in _LOGIN_FAILURES
    finally:
        with app.app_context():
            db.session.query(MasterTwoFactor).filter_by(master_user_id=user_id).delete(synchronize_session=False)
            db.session.delete(db.session.get(LicMasterUser, user_id))
            db.session.commit()


def test_journal_entry_model_allows_audited_cancellation_state(app):
    from models.accounting import JournalEntry

    constraint = next(
        c for c in JournalEntry.__table__.constraints
        if c.name == "ck_journal_entry_status"
    )
    assert "cancelled" in str(constraint.sqltext)
