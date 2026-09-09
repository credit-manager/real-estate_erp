import importlib

import pytest
from werkzeug.security import check_password_hash


def _target(password_hash="known-hash"):
    class Target:
        username = "admin"
        must_change_password = True
        email = "admin@example.com"
        full_name = "Admin"
        role = "admin"
        globals()["_password_hash"] = password_hash
    return Target()


def test_production_cloud_refuses_missing_bootstrap_password(monkeypatch):
    import config
    import models.user as user_module

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "IS_FROZEN", False)
    monkeypatch.delenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="bootstrap admin credential"):
        user_module._configure_bootstrap_admin(_target())


def test_development_keeps_seed_compatibility(monkeypatch):
    import config
    import models.user as user_module

    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.delenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    target = _target()
    original = target.password_hash
    user_module._configure_bootstrap_admin(target)
    assert target.password_hash == original


def test_production_bootstrap_password_is_hashed(monkeypatch):
    import config
    import models.user as user_module

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "IS_FROZEN", False)
    monkeypatch.setenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", "a-strong-bootstrap-password")
    target = _target("legacy-hash")
    user_module._configure_bootstrap_admin(target)
    assert target.password_hash != "legacy-hash"
    assert check_password_hash(target.password_hash, "a-strong-bootstrap-password")
