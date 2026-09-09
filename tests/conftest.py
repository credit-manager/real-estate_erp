# -*- coding: utf-8 -*-
"""Test fixtures for ERP Control Center tests.

Provides Flask test client, authenticated sessions, and DB setup/teardown.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    """Set deterministic CI-safe environment variables before imports."""
    os.environ["DB_USER"] = os.environ.get("DB_USER", "mokawlat_user")
    os.environ["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "0100")
    os.environ["DB_HOST"] = os.environ.get("DB_HOST", "127.0.0.1")
    os.environ["DB_PORT"] = os.environ.get("DB_PORT", "5432")
    os.environ["DB_NAME"] = os.environ.get("DB_NAME", "dynamicpro")
    os.environ["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!!"
    )
    os.environ["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "test-application-secret-key-for-testing-only"
    )
    os.environ["DYNAMICPRO_ENV"] = os.environ.get("DYNAMICPRO_ENV", "test")


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    application.config["SESSION_COOKIE_SECURE"] = False
    yield application


@pytest.fixture(scope="function")
def client(app):
    """Create test client with clean session per test."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_client(client, app):
    """Return a test client authenticated against a seeded test administrator."""
    from models import User
    from database import db
    from werkzeug.security import generate_password_hash

    username = f"test_admin_{uuid.uuid4().hex[:8]}"
    password = "Test-only-password-9381!"
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
        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)
            db.session.commit()


@pytest.fixture(scope="session")
def _db(app):
    """Ensure DB tables exist."""
    from database import db

    with app.app_context():
        db.create_all()
        yield db
