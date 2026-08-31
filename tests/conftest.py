"""Shared test fixtures for DynamicPro ERP test suite."""
import os
import sys
import pytest
from datetime import date, timedelta

# Ensure project root is on sys.path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

os.environ.setdefault("DB_PASSWORD", "0100")
os.environ.setdefault("DB_NAME", "dynamicpro")


@pytest.fixture(scope="session")
def app():
    """Create application for testing (session-scoped for speed)."""
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["SERVER_ACCESS_PASSWORD"] = ""
    return application


@pytest.fixture(autouse=True)
def _setup_db(app):
    """Ensure DB tables exist before each test."""
    from database import db as _db
    with app.app_context():
        _db.create_all()
        yield
        _db.session.rollback()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def auth_client(client, app):
    """Authenticated test client — logs in as admin and bypasses forced password change."""
    resp = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    with client.session_transaction() as sess:
        with app.app_context():
            from database import db
            from models import User
            u = db.session.get(User, sess.get("user_id"))
            if u and u.must_change_password:
                u.must_change_password = False
                db.session.commit()
    return client


# ==================== Reusable helper fixtures ====================


@pytest.fixture()
def sample_project(auth_client):
    """Create and return a sample project dict."""
    resp = auth_client.post("/api/projects", json={
        "name": f"مشروع اختبار-{os.urandom(3).hex()}",
        "location": "الرياض",
        "status": "active",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture()
def sample_building(auth_client, sample_project):
    """Create and return a sample building dict under sample_project."""
    resp = auth_client.post("/api/realestate/buildings", json={
        "project_id": sample_project["id"],
        "name": f"مبنى اختبار-{os.urandom(3).hex()}",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture()
def sample_unit(auth_client, sample_project, sample_building):
    """Create and return a sample unit dict."""
    resp = auth_client.post("/api/units", json={
        "unit_code": f"TST-{os.urandom(5).hex()}",
        "project_id": sample_project["id"],
        "building_id": sample_building["id"],
        "price": 500000,
        "area": 120,
        "status": "available",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


@pytest.fixture()
def sample_customer(auth_client):
    """Create and return a sample customer dict."""
    resp = auth_client.post("/api/customers", json={
        "full_name": f"عميل اختبار-{os.urandom(3).hex()}",
        "phone": "0501234567",
        "email": "test@example.com",
        "type": "individual",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


@pytest.fixture()
def sample_supplier(auth_client):
    """Create and return a sample supplier dict."""
    resp = auth_client.post("/api/suppliers", json={
        "company_name": f"شركة اختبار-{os.urandom(3).hex()}",
        "contact_name": "مدير المبيعات",
        "phone": "0509876543",
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


@pytest.fixture()
def sample_invoice(auth_client, sample_customer):
    """Create and return a sample sales invoice dict."""
    resp = auth_client.post("/api/invoices", json={
        "invoice_type": "sales",
        "customer_id": sample_customer["id"],
        "amount": 10000,
        "issue_date": date.today().isoformat(),
    })
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()


@pytest.fixture()
def future_date():
    """Return a date 30 days in the future as ISO string."""
    return (date.today() + timedelta(days=30)).isoformat()


@pytest.fixture()
def today_iso():
    """Return today's date as ISO string."""
    return date.today().isoformat()
