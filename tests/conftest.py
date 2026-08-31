# -*- coding: utf-8 -*-
"""Test fixtures for ERP Control Center tests.

Provides Flask test client, authenticated sessions, and DB setup/teardown.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    """Set environment variables before any imports."""
    os.environ["DB_USER"] = os.environ.get("DB_USER", "mokawlat_user")
    os.environ["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "0100")
    os.environ["DB_HOST"] = os.environ.get("DB_HOST", "127.0.0.1")
    os.environ["DB_PORT"] = os.environ.get("DB_PORT", "5432")
    os.environ["DB_NAME"] = os.environ.get("DB_NAME", "dynamicpro")
    os.environ["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!!"
    )


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    yield app


@pytest.fixture(scope="function")
def client(app):
    """Create test client with clean session per test."""
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="session")
def _db(app):
    """Ensure DB tables exist."""
    from database import db
    with app.app_context():
        db.create_all()
        yield db
