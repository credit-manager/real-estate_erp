import pytest
from werkzeug.security import check_password_hash, generate_password_hash


def _target(password_hash=None):
    class Target:
        username = "admin"
        must_change_password = True
        email = "admin@mokawlat.com"
        full_name = "Admin"
        role = "admin"

    t = Target()
    t.password_hash = password_hash if password_hash is not None else generate_password_hash("admin123")
    return t


def _call(target):
    """Invoke the SQLAlchemy mapper-event listener with its real signature."""
    import models.user as user_module

    return user_module._configure_bootstrap_admin(None, None, target)


def test_production_cloud_refuses_missing_bootstrap_password(monkeypatch):
    import config

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "IS_FROZEN", False)
    monkeypatch.delenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="default admin credential"):
        _call(_target())


def test_development_keeps_seed_compatibility(monkeypatch):
    import config

    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.delenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    target = _target()
    original = target.password_hash
    _call(target)
    assert target.password_hash == original


def test_production_bootstrap_password_is_hashed(monkeypatch):
    import config

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "IS_FROZEN", False)
    monkeypatch.setenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", "a-strong-bootstrap-password")
    target = _target("legacy-hash")
    _call(target)
    assert target.password_hash != "legacy-hash"
    assert check_password_hash(target.password_hash, "a-strong-bootstrap-password")
