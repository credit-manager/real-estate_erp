#!/usr/bin/env python3
"""Apply deterministic production hardening edits to the legacy app.py.

The repository historically contained startup seeding with a known password and
an in-process Flask-Limiter backend. This script performs exact replacements so
the changes are reviewable and repeatable, without reformatting app.py.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

text = APP.read_text(encoding="utf-8")
original = text

old_admin = '''    if not User.query.filter_by(username="admin").first():\n        admin = User(\n            username="admin", email="admin@mokawlat.com", full_name="مدير النظام",\n            role="admin", password_hash=generate_password_hash("admin123"), must_change_password=True,\n        )\n        db.session.add(admin)\n        db.session.commit()\n'''
new_admin = '''    if not User.query.filter_by(username="admin").first():\n        import os\n        from werkzeug.security import generate_password_hash\n        from runtime_hardening import secure_bootstrap_admin\n\n        password = secure_bootstrap_admin()\n        if password is None:\n            if os.environ.get("DYNAMICPRO_ENV", "").lower() in {"production", "prod"} and not getattr(sys, "frozen", False):\n                raise RuntimeError(\n                    "Production bootstrap requires DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD; refusing to create a default administrator."\n                )\n            password = secure_bootstrap_admin(generate_random=True)\n\n        admin = User(\n            username="admin", email="admin@mokawlat.com", full_name="مدير النظام",\n            role="admin", password_hash=generate_password_hash(password), must_change_password=True,\n        )\n        db.session.add(admin)\n        db.session.commit()\n'''
if old_admin not in text:
    raise SystemExit("admin bootstrap block not found; refusing a partial transformation")
text = text.replace(old_admin, new_admin, 1)

old_master = '''    # Seed master admin for licensing panel (desktop mode)\n    from licensing.models import LicMasterUser\n    if not LicMasterUser.query.filter_by(email="admin@mokawlat.com").first():\n        master = LicMasterUser(\n            email="admin@mokawlat.com",\n            password_hash=generate_password_hash("admin123"),\n            full_name="Super Admin",\n            role="super_admin",\n            is_active=True,\n        )\n        db.session.add(master)\n        db.session.commit()\n'''
new_master = '''    # Seed master admin for the licensing panel without a hard-coded password.\n    from licensing.models import LicMasterUser\n    if not LicMasterUser.query.filter_by(email="admin@mokawlat.com").first():\n        from runtime_hardening import secure_bootstrap_admin\n        password = secure_bootstrap_admin()\n        if password is None:\n            import os\n            if os.environ.get("DYNAMICPRO_ENV", "").lower() in {"production", "prod"} and not getattr(sys, "frozen", False):\n                raise RuntimeError(\n                    "Production master bootstrap requires DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD."\n                )\n            password = secure_bootstrap_admin(generate_random=True)\n        master = LicMasterUser(\n            email="admin@mokawlat.com",\n            password_hash=generate_password_hash(password),\n            full_name="Super Admin",\n            role="super_admin",\n            is_active=True,\n        )\n        db.session.add(master)\n        db.session.commit()\n'''
if old_master not in text:
    raise SystemExit("master bootstrap block not found; refusing a partial transformation")
text = text.replace(old_master, new_master, 1)

old_limiter = '''    limiter = Limiter(\n        get_remote_address,\n        app=app,\n        default_limits=["200 per minute", "50 per second"],\n        storage_uri="memory://",\n        strategy="fixed-window",\n        key_prefix="rl:"\n    )\n'''
new_limiter = '''    _rate_storage = config.RATELIMIT_STORAGE_URI or "memory://"\n    if config.IS_PRODUCTION and _rate_storage == "memory://":\n        raise RuntimeError("Distributed rate limiting storage is mandatory in production.")\n    limiter = Limiter(\n        get_remote_address,\n        app=app,\n        default_limits=["200 per minute", "50 per second"],\n        storage_uri=_rate_storage,\n        strategy="fixed-window",\n        key_prefix="rl:"\n    )\n'''
if old_limiter not in text:
    raise SystemExit("rate limiter block not found; refusing a partial transformation")
text = text.replace(old_limiter, new_limiter, 1)

# Add readiness endpoints exactly once, immediately after create_app starts.
marker = 'def create_app():\n'
insert = '''def create_app():\n'''
if text.count('def create_app():\n') != 1:
    raise SystemExit("unexpected create_app definition count")
if 'def _health_payload' not in text:
    insert += '''    def _health_payload(ready: bool):\n        return {"status": "ready" if ready else "ok", "service": "dynamicpro", "version": os.environ.get("DYNAMICPRO_VERSION", "dev")}\n\n    @app.get("/health")\n    def health_check():\n        return _health_payload(True), 200\n\n'''
    # Since app isn't constructed until root selection, these routes cannot be\n    # declared before the Flask object exists. The helper is intentionally kept\n    # as an internal marker only and is injected below after app construction.\n\n# Instead of complex AST rewriting, add health route after static config is ready.
route_marker = '    db.init_app(app)\n'
if '    @app.get("/health")' not in text:
    health_routes = '''    @app.get("/health")\n    def health_check():\n        return {"status": "ok", "service": "dynamicpro", "version": os.environ.get("DYNAMICPRO_VERSION", "dev")}, 200\n\n    @app.get("/ready")\n    def readiness_check():\n        try:\n            from sqlalchemy import text\n            db.session.execute(text("SELECT 1"))\n            return {"status": "ready", "service": "dynamicpro"}, 200\n        except Exception:\n            return {"status": "not_ready", "service": "dynamicpro"}, 503\n\n'''
    text = text.replace(route_marker, route_marker + health_routes, 1)

if text == original:
    raise SystemExit("hardening script made no changes")
APP.write_text(text, encoding="utf-8")
print("app.py production hardening applied")
