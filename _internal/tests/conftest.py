# -*- coding: utf-8 -*-
"""Pytest configuration and fixtures for DynamicPro ERP tests."""
import os
import sys
import tempfile
import types

import pytest

# Ensure _internal is on sys.path so modules can be imported
_INTERNAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _INTERNAL not in sys.path:
    sys.path.insert(0, _INTERNAL)

os.environ["DYNAMICPRO_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"

# Mock runtime_hardening module before any app imports
if "runtime_hardening" not in sys.modules:
    _rh = types.ModuleType("runtime_hardening")
    _rh.install = lambda: None
    sys.modules["runtime_hardening"] = _rh

# Mock auditlog module (not in extracted PyInstaller bundle)
if "auditlog" not in sys.modules:
    _al = types.ModuleType("auditlog")
    _al.log_action = lambda *a, **kw: None
    sys.modules["auditlog"] = _al


@pytest.fixture(scope="session")
def app():
    """Create a Flask application configured for testing with SQLite."""
    from flask import Flask

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["SERVER_NAME"] = "localhost"

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    from database import db
    db.init_app(flask_app)

    with flask_app.app_context():
        # Import all models so they register with SQLAlchemy
        import models  # noqa: F401
        import security.models  # noqa: F401
        import licensing.models  # noqa: F401
        db.create_all()

        # Register auth blueprint
        from routes.auth import auth_bp
        flask_app.register_blueprint(auth_bp)

        # Register pages blueprint (routes/pages.py)
        from routes.pages import pages_bp
        flask_app.register_blueprint(pages_bp)

        # Register settings blueprint (routes/settings.py)
        from routes.settings import settings_bp
        flask_app.register_blueprint(settings_bp)

        yield flask_app
        db.drop_all()

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture(scope="session")
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """Rollback-safe database session for each test."""
    from database import db as _db
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        from sqlalchemy.orm import scoped_session, sessionmaker
        session_factory = sessionmaker(bind=connection)
        session = scoped_session(session_factory)
        original = _db.session
        _db.session = session
        yield session
        transaction.rollback()
        connection.close()
        session.remove()
        _db.session = original
