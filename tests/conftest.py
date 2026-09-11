# -*- coding: utf-8 -*-
"""Test fixtures for ERP Control Center tests.

Provides Flask test clients, isolated employee sessions, and fully MFA-verified
master-admin sessions without production bootstrap credentials.
"""
import os
import secrets
import sys
import uuid
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    os.environ["DB_USER"] = os.environ.get("DB_USER", "test_user")
    os.environ.setdefault("DB_PASSWORD", secrets.token_urlsafe(24))
    os.environ["DB_HOST"] = os.environ.get("DB_HOST", "127.0.0.1")
    os.environ["DB_PORT"] = os.environ.get("DB_PORT", "5432")
    os.environ["DB_NAME"] = os.environ.get("DB_NAME", "test_db")
    os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test-application-secret-key-for-testing-only")
    os.environ["DYNAMICPRO_ENV"] = os.environ.get("DYNAMICPRO_ENV", "test")
    # Disable heartbeat throttling in tests (sequential heartbeats per test)
    os.environ["REMOTE_HEARTBEAT_MIN_INTERVAL_SEC"] = os.environ.get(
        "REMOTE_HEARTBEAT_MIN_INTERVAL_SEC", "0")


@pytest.fixture(scope="session")
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["SESSION_COOKIE_SECURE"] = False
    yield application


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_client(client, app):
    from models import AuditLog, LicenseActivity, User
    from database import db
    from werkzeug.security import generate_password_hash

    username = f"test_admin_{uuid.uuid4().hex[:8]}"
    password = secrets.token_urlsafe(24)
    with app.app_context():
        user = User(
            username=username,
            email=f"{username}@example.test",
            full_name="Test Administrator",
            role="admin",
            password_hash=generate_password_hash(password),
            is_active=True,
            must_change_password=False,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.get_json()
    yield client

    with app.app_context():
        from sqlalchemy import text as _text
        # Null out any FK references to the test user (e.g. approval
        # requests auto-created by workflow submission) before delete.
        try:
            _fks = db.session.execute(_text(
                "SELECT tc.table_name, kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON ccu.constraint_name = tc.constraint_name "
                "WHERE tc.constraint_type = 'FOREIGN KEY' "
                "  AND ccu.table_name = 'users' "
                "  AND ccu.column_name = 'id'"
            )).fetchall()
            for _tbl, _col in _fks:
                try:
                    db.session.execute(
                        _text(f'UPDATE "{_tbl}" SET "{_col}" = NULL WHERE "{_col}" = :uid'),
                        {"uid": user_id},
                    )
                except Exception:
                    db.session.rollback()
        except Exception:
            db.session.rollback()
        db.session.query(AuditLog).filter(AuditLog.user_id == user_id).delete(synchronize_session=False)
        db.session.query(LicenseActivity).filter(LicenseActivity.user_id == user_id).delete(synchronize_session=False)
        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)
        db.session.commit()


@pytest.fixture(scope="function")
def master_client(client, app):
    from database import db
    from licensing.models import LicMasterUser, LicActivityLog
    from security.models import MasterSession, MasterTwoFactor, MasterUserRole, MasterAuditLog, SecurityEvent
    from werkzeug.security import generate_password_hash
    import pyotp

    email = f"master_test_{uuid.uuid4().hex[:8]}@example.test"
    password = secrets.token_urlsafe(24)
    mfa_secret = pyotp.random_base32()
    with app.app_context():
        user = LicMasterUser(
            email=email,
            password_hash=generate_password_hash(password),
            full_name="Test Master",
            role="super_admin",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        mfa = MasterTwoFactor(
            master_user_id=user.id,
            secret=mfa_secret,
            enabled_at=datetime.utcnow(),
            verified_at=datetime.utcnow(),
        )
        db.session.add(mfa)
        db.session.commit()
        user_id = user.id

    response = client.post("/admin/login", json={"email": email, "password": password})
    assert response.status_code == 401, response.get_json()
    assert response.get_json().get("requires_2fa") is True
    code = pyotp.TOTP(mfa_secret).now()
    response = client.post("/admin/security/2fa/verify", json={"code": code})
    assert response.status_code == 200, response.get_json()
    assert response.get_json().get("success") is True
    yield client

    with app.app_context():
        db.session.query(MasterSession).filter(MasterSession.master_user_id == user_id).delete(synchronize_session=False)
        db.session.query(MasterUserRole).filter(MasterUserRole.master_user_id == user_id).delete(synchronize_session=False)
        db.session.query(MasterAuditLog).filter(MasterAuditLog.master_user_id == user_id).delete(synchronize_session=False)
        db.session.query(SecurityEvent).filter(SecurityEvent.master_user_id == user_id).delete(synchronize_session=False)
        db.session.query(LicActivityLog).filter(LicActivityLog.actor_id == user_id).delete(synchronize_session=False)
        db.session.query(MasterTwoFactor).filter(MasterTwoFactor.master_user_id == user_id).delete(synchronize_session=False)
        user = db.session.get(LicMasterUser, user_id)
        if user is not None:
            db.session.delete(user)
        db.session.commit()


@pytest.fixture(scope="session")
def _db(app):
    from database import db
    with app.app_context():
        db.create_all()
        yield db


# ── Shared sample-data fixtures (used across module test files) ────


@pytest.fixture(scope="function")
def future_date():
    from datetime import date, timedelta

    return (date.today() + timedelta(days=30)).isoformat()


@pytest.fixture(scope="function")
def sample_project(auth_client):
    resp = auth_client.post("/api/projects", json={
        "name": f"مشروع اختبار {uuid.uuid4().hex[:6]}",
        "location": "الرياض",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture(scope="function")
def sample_building(auth_client, sample_project):
    resp = auth_client.post("/api/realestate/buildings", json={
        "project_id": sample_project["id"],
        "name": "مبنى اختبار",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture(scope="function")
def sample_unit(auth_client, sample_project, sample_building):
    resp = auth_client.post("/api/units", json={
        "unit_code": f"TST-{uuid.uuid4().hex[:8].upper()}",
        "project_id": sample_project["id"],
        "building_id": sample_building["id"],
        "price": 500000,
        "status": "available",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture(scope="function")
def sample_customer(auth_client):
    resp = auth_client.post("/api/customers", json={
        "full_name": f"عميل اختبار {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


@pytest.fixture(scope="function")
def sample_supplier(auth_client):
    resp = auth_client.post("/api/suppliers", json={
        "company_name": f"مورد اختبار {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture(scope="function")
def sample_company(app):
    """Minimal licensed company (plan + active subscription) for admin tests."""
    from datetime import date, timedelta

    from database import db
    from licensing.models import LicCompany, LicPlan, LicSubscription

    with app.app_context():
        plan = LicPlan.query.filter_by(code="basic").first()
        if not plan:
            plan = LicPlan(
                code="basic", name="Basic", name_ar="الأساسية",
                max_users=5, max_projects=10, max_storage_mb=1024,
                modules={}, is_active=True, sort_order=0,
            )
            db.session.add(plan)
            db.session.flush()
        tag = uuid.uuid4().hex[:8]
        company = LicCompany(
            name=f"Test Co {tag}", name_ar=f"شركة اختبار {tag}",
            email=f"testco-{tag}@example.test",
            db_name=f"testdb_{tag}", port=29999, status="active",
        )
        db.session.add(company)
        db.session.flush()
        today = date.today()
        db.session.add(LicSubscription(
            company_id=company.id, plan_id=plan.id,
            start_date=today, end_date=today + timedelta(days=30),
            status="active",
        ))
        db.session.commit()
        return {"id": company.id, "name": company.name, "status": company.status}
