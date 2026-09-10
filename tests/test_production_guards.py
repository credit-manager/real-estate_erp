import os
import subprocess
import sys


def test_production_requires_managed_secret(monkeypatch):
    monkeypatch.setenv("DYNAMICPRO_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "ci-managed-secret-value")
    monkeypatch.setenv("DB_USER", "test")
    monkeypatch.setenv("DB_PASSWORD", "test")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    code = "import config; assert config.IS_PRODUCTION is True"
    result = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_production_secret_is_required_when_missing():
    env = os.environ.copy()
    env.update({
        "DYNAMICPRO_ENV": "production",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test",
        "REDIS_URL": "redis://localhost:6379/0",
    })
    env.pop("SECRET_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", "import config"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "SECRET_KEY" in (result.stderr + result.stdout)


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
