import os
import secrets
import sys

try:
    from dotenv import load_dotenv

    _env_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), ".env")
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

IS_FROZEN = bool(getattr(sys, "frozen", False))
RUNTIME_ENV = os.environ.get("DYNAMICPRO_ENV", "production" if IS_FROZEN else "development").strip().lower()
IS_PRODUCTION = RUNTIME_ENV in {"production", "prod"}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

if IS_FROZEN:
    USER_DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~"),
        "Dynamic Pro ERP",
        "Data",
    )
else:
    USER_DATA_DIR = os.environ.get(
        "DYNAMICPRO_DATA_DIR",
        os.path.join(os.path.expanduser("~"), ".dynamicpro"),
    )

COMPANY_ID = os.environ.get("COMPANY_ID", "").strip()
COMPANY_PORT = os.environ.get("COMPANY_PORT", "").strip()
IS_COMPANY_INSTANCE = bool(COMPANY_ID)

os.makedirs(USER_DATA_DIR, exist_ok=True)

if IS_FROZEN:
    DB_PATH = os.path.join(USER_DATA_DIR, "dynamicpro.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH.replace(chr(92), '/') }"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
    DB_USER = DB_PASSWORD = DB_HOST = DB_PORT = DB_NAME = ""
else:
    DB_USER = os.environ.get("DB_USER", "mokawlat_user")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "dynamicpro")
    _DB_PW_FILE = os.path.join(USER_DATA_DIR, ".db_password")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "").strip()

    if not DB_PASSWORD and not IS_PRODUCTION and os.path.isfile(_DB_PW_FILE):
        try:
            with open(_DB_PW_FILE, "r", encoding="utf-8") as fh:
                DB_PASSWORD = fh.read().strip()
        except OSError:
            DB_PASSWORD = ""

    if not DB_PASSWORD:
        if IS_PRODUCTION:
            raise RuntimeError("DB_PASSWORD must be supplied explicitly in production.")
        DB_PASSWORD = secrets.token_urlsafe(32)
        try:
            with open(_DB_PW_FILE, "w", encoding="utf-8") as fh:
                fh.write(DB_PASSWORD)
            try:
                os.chmod(_DB_PW_FILE, 0o600)
            except OSError:
                pass
        except OSError:
            pass

    if COMPANY_ID:
        try:
            from sqlalchemy import create_engine, text

            _admin_uri = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/dynamicpro"
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
                elif IS_PRODUCTION:
                    raise RuntimeError(f"No active database registry entry for company {COMPANY_ID}.")
        except RuntimeError:
            raise
        except Exception as exc:
            if IS_PRODUCTION:
                raise RuntimeError(f"Unable to resolve production database for company {COMPANY_ID}.") from exc

    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}

_SECRET_FILE = os.path.join(USER_DATA_DIR, ".secret_key")
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()

if not SECRET_KEY and not IS_PRODUCTION and os.path.isfile(_SECRET_FILE):
    try:
        with open(_SECRET_FILE, "r", encoding="utf-8") as fh:
            SECRET_KEY = fh.read().strip()
    except OSError:
        SECRET_KEY = ""

if not SECRET_KEY:
    if IS_PRODUCTION and not IS_FROZEN:
        raise RuntimeError("SECRET_KEY must be supplied explicitly in production.")
    SECRET_KEY = secrets.token_hex(32)
    try:
        with open(_SECRET_FILE, "w", encoding="utf-8") as fh:
            fh.write(SECRET_KEY)
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass

SEND_FILE_MAX_AGE_DEFAULT = 0
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = IS_PRODUCTION and not IS_FROZEN
PERMANENT_SESSION_LIFETIME = 8 * 3600

IS_MASTER_INSTANCE = not COMPANY_ID
