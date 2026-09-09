"""Runtime hardening hooks loaded before application factories and models."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

_PATCHED = False


def _bootstrap_password() -> str:
    return os.environ.get("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", "").strip()


def _is_default_user(obj: Any) -> bool:
    return (
        obj.__class__.__name__ == "User"
        and (getattr(obj, "username", "") or "").strip().lower() == "admin"
        and (getattr(obj, "email", "") or "").strip().lower() == "admin@mokawlat.com"
    )


def _is_default_master(obj: Any) -> bool:
    return (
        obj.__class__.__name__ == "LicMasterUser"
        and (getattr(obj, "email", "") or "").strip().lower() == "admin@mokawlat.com"
    )


def _persist_first_run_password(user_data_dir: str, password: str, filename: str) -> None:
    path = Path(user_data_dir) / filename
    if path.exists():
        return
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Dynamic Pro ERP first-run administrator\n"
        "username=admin\n"
        f"password={password}\n"
        "change this password immediately after first login\n",
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _harden_new_objects(session: Session, _flush_context: Any, instances: Any) -> None:
    """Remove or harden legacy hard-coded bootstrap accounts before INSERT."""
    from config import IS_FROZEN, IS_PRODUCTION, USER_DATA_DIR

    for obj in list(session.new):
        if _is_default_user(obj):
            if not IS_PRODUCTION:
                continue
            password = _bootstrap_password()
            if password:
                if len(password) < 14:
                    raise RuntimeError("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD must be at least 14 characters.")
                obj.password_hash = generate_password_hash(password)
                obj.must_change_password = True
            elif IS_FROZEN:
                password = secrets.token_urlsafe(18)
                obj.password_hash = generate_password_hash(password)
                obj.must_change_password = True
                _persist_first_run_password(str(USER_DATA_DIR), password, "FIRST_RUN_ADMIN.txt")
            else:
                session.expunge(obj)

        if _is_default_master(obj):
            if not IS_PRODUCTION:
                continue
            password = _bootstrap_password()
            if password:
                if len(password) < 14:
                    raise RuntimeError("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD must be at least 14 characters.")
                obj.password_hash = generate_password_hash(password)
            elif IS_FROZEN:
                password = secrets.token_urlsafe(18)
                obj.password_hash = generate_password_hash(password)
                _persist_first_run_password(str(USER_DATA_DIR), password, "FIRST_RUN_MASTER.txt")
            else:
                session.expunge(obj)


def _patch_rate_limiter() -> None:
    """Honor REDIS_URL/RATELIMIT_STORAGE_URI even if the legacy app asks for memory://."""
    global _PATCHED
    if _PATCHED:
        return
    try:
        from flask_limiter import Limiter as OriginalLimiter
    except ImportError:
        return

    class HardenedLimiter(OriginalLimiter):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            configured = os.environ.get("RATELIMIT_STORAGE_URI") or os.environ.get("REDIS_URL")
            if configured:
                kwargs["storage_uri"] = configured
            elif os.environ.get("DYNAMICPRO_ENV", "").lower() in {"prod", "production"}:
                raise RuntimeError("Distributed production rate limiting requires REDIS_URL or RATELIMIT_STORAGE_URI.")
            super().__init__(*args, **kwargs)

    import flask_limiter

    flask_limiter.Limiter = HardenedLimiter
    _PATCHED = True


def install() -> None:
    if not event.contains(Session, "before_flush", _harden_new_objects):
        event.listen(Session, "before_flush", _harden_new_objects)
    _patch_rate_limiter()
