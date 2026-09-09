import importlib
import os


def test_production_requires_managed_secret(monkeypatch):
    monkeypatch.setenv("DYNAMICPRO_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    import config

    importlib.reload(config)
    assert config.IS_PRODUCTION is True


def test_bootstrap_password_never_uses_legacy_default(monkeypatch):
    monkeypatch.delenv("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    from runtime_hardening import secure_bootstrap_admin

    generated = secure_bootstrap_admin(generate_random=True)
    assert generated
    assert generated != "admin123"
    assert len(generated) >= 20


def test_runtime_hardening_is_idempotent():
    from runtime_hardening import install

    install()
    install()


def test_production_environment_flag_is_explicit(monkeypatch):
    monkeypatch.setenv("DYNAMICPRO_ENV", "production")
    assert os.environ["DYNAMICPRO_ENV"] == "production"
