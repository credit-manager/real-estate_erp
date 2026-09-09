import os
import secrets
import sys
from pathlib import Path

# Load optional local development environment. Production deployments must use
# the process environment / secret manager and never persist credentials in git.
try:
    from dotenv import load_dotenv

    _env_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), ".env")
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

IS_FROZEN = getattr(sys, "frozen", False)
DYNAMICPRO_ENV = os.environ.get("DYNAMICPRO_ENV", "development").strip().lower()
IS_PRODUCTION = DYNAMICPRO_ENV in {"production", "prod"}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

if IS_FROZEN:
    USER_DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or os.path.expanduser("~"),
        "Dynamic Pro ERP",
    )
else:
    _state_root = (
        os.environ.get("DYNAMICPRO_DATA_DIR")
        or os.environ.get("XDG_STATE_HOME")
        or os.path.join(os.path.expanduser("~"), ".dynamicpro")
    )
    USER_DATA_DIR = os.path.abspath(_state_root)

COMPANY_ID = os.environ.get("COMPANY_ID", "")
COMPANY_PORT = os.environ.get("COMPANY_PORT", "")
IS_COMPANY_INSTANCE = bool(COMPANY_ID)

if IS_FROZEN:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(USER_DATA_DIR, "dynamicpro.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
    DB_USER = ""
    DB_PASSWORD = ""
    DB_HOST = ""
    DB_PORT = ""
    DB_NAME = ""
else:
    DB_USER = os.environ.get("DB_USER", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "dynamicpro")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

    if IS_PRODUCTION and not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD is required in production; refusing to start without managed credentials.")
    if not DB_USER:
        if IS_PRODUCTION:
            raise RuntimeError("DB_USER is required in production.")
        DB_USER = "mokawlat_user"

    if COMPANY_ID:
        try:
            from sqlalchemy import create_engine, text

            if not DB_PASSWORD:
                raise RuntimeError("A database password is required before company database discovery.")
            _admin_uri = (
                f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/dynamicpro"
            )
            _eng = create_engine(_admin_uri, isolation_level="AUTOCOMMIT")
            with _eng.connect() as _conn:
                _row = _conn.execute(
                    text(
                        "SELECT db_name, db_host, db_port FROM lic_database_registry "
                        "WHERE company_id = :cid AND status = 'active' LIMIT 1"
                    ),
                    {"cid": int(COMPANY_ID)},
                ).fetchone()
                if _row:
                    DB_NAME = _row[0]
                    DB_HOST = _row[1] or DB_HOST
                    DB_PORT = str(_row[2]) if _row[2] else DB_PORT
        except Exception as exc:
            if IS_PRODUCTION:
                raise RuntimeError("Unable to resolve the active company database.") from exc
            print(f"[config] WARNING: company database lookup failed: {exc}")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Session signing secret: explicit in Cloud production, durable local secret for
# development/Desktop only. Never create a production secret in the repository.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION and not IS_FROZEN:
        raise RuntimeError("SECRET_KEY is required in production; configure a managed secret.")

    _secret_file = Path(USER_DATA_DIR) / (f".secret_key_{COMPANY_ID}" if COMPANY_ID else ".secret_key")
    try:
        USER_DATA_DIR and os.makedirs(USER_DATA_DIR, exist_ok=True)
        SECRET_KEY = _secret_file.read_text(encoding="utf-8").strip() if _secret_file.is_file() else ""
        if not SECRET_KEY:
            SECRET_KEY = secrets.token_hex(32)
            _secret_file.write_text(SECRET_KEY, encoding="utf-8")
            try:
                os.chmod(_secret_file, 0o600)
            except OSError:
                pass
    except OSError as exc:
        raise RuntimeError("Unable to persist the local application secret securely.") from exc

SEND_FILE_MAX_AGE_DEFAULT = 0
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = bool(IS_PRODUCTION and not IS_FROZEN)
PERMANENT_SESSION_LIFETIME = 8 * 3600

# Redis-backed rate limiting is mandatory for production multi-instance Cloud.
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI") or os.environ.get("REDIS_URL", "")
if IS_PRODUCTION and not RATELIMIT_STORAGE_URI:
    raise RuntimeError("REDIS_URL or RATELIMIT_STORAGE_URI is required in production for distributed rate limiting.")

IS_MASTER_INSTANCE = not COMPANY_ID
