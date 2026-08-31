import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ── وضع التشغيل ──
COMPANY_ID = os.environ.get("COMPANY_ID", "")
COMPANY_PORT = os.environ.get("COMPANY_PORT", "")
IS_COMPANY_INSTANCE = bool(COMPANY_ID)

# إعداد قاعدة البيانات
DB_USER = os.environ.get("DB_USER", "mokawlat_user")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "dynamicpro")

_DB_PW_FILE = os.path.join(BASE_DIR, ".db_password")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
if not DB_PASSWORD and os.path.isfile(_DB_PW_FILE):
    try:
        with open(_DB_PW_FILE, "r", encoding="utf-8") as fh:
            DB_PASSWORD = fh.read().strip()
    except OSError:
        DB_PASSWORD = ""
if not DB_PASSWORD:
    DB_PASSWORD = secrets.token_urlsafe(24)
    try:
        with open(_DB_PW_FILE, "w", encoding="utf-8") as fh:
            fh.write(DB_PASSWORD)
        try:
            os.chmod(_DB_PW_FILE, 0o600)
        except OSError:
            pass
        print("[config] DB password generated and saved to .db_password")
    except OSError:
        pass

# ── إذا كان هناك COMPANY_ID، نبحث عن قاعدة بيانات الشركة ──
if COMPANY_ID:
    try:
        from sqlalchemy import create_engine, text
        _admin_uri = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/dynamicpro"
        _eng = create_engine(_admin_uri, isolation_level="AUTOCOMMIT")
        with _eng.connect() as _conn:
            _row = _conn.execute(text(
                "SELECT db_name, db_host, db_port FROM lic_database_registry "
                "WHERE company_id = :cid AND status = 'active' LIMIT 1"
            ), {"cid": int(COMPANY_ID)}).fetchone()
            if _row:
                DB_NAME = _row[0]
                DB_HOST = _row[1] or DB_HOST
                DB_PORT = str(_row[2]) if _row[2] else DB_PORT
                print(f"[config] Company {COMPANY_ID}: DB={DB_NAME} @ {DB_HOST}:{DB_PORT}")
            else:
                print(f"[config] WARNING: No active DB found for company {COMPANY_ID}, using default")
    except Exception as e:
        print(f"[config] WARNING: Could not lookup company DB: {e}")

SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ── Per-company SECRET_KEY (CRITICAL #1) ──
# كل شركة لها مفتاح جلسات مستقل لمنع اختراق عناصر الجلسة بين الشركات
if COMPANY_ID:
    _company_key_file = os.path.join(BASE_DIR, f".secret_key_{COMPANY_ID}")
    if os.environ.get("SECRET_KEY"):
        SECRET_KEY = os.environ["SECRET_KEY"]
    elif os.path.isfile(_company_key_file):
        with open(_company_key_file, "r", encoding="utf-8") as fh:
            SECRET_KEY = fh.read().strip()
    else:
        SECRET_KEY = secrets.token_hex(32)
        try:
            with open(_company_key_file, "w", encoding="utf-8") as fh:
                fh.write(SECRET_KEY)
        except OSError:
            pass
else:
    _SECRET_FILE = os.path.join(BASE_DIR, ".secret_key")
    if os.environ.get("SECRET_KEY"):
        SECRET_KEY = os.environ["SECRET_KEY"]
    elif os.path.isfile(_SECRET_FILE):
        with open(_SECRET_FILE, "r", encoding="utf-8") as fh:
            SECRET_KEY = fh.read().strip()
    else:
        SECRET_KEY = secrets.token_hex(32)
        try:
            with open(_SECRET_FILE, "w", encoding="utf-8") as fh:
                fh.write(SECRET_KEY)
        except OSError:
            pass

SEND_FILE_MAX_AGE_DEFAULT = 0

# ── Session cookie isolation (HIGH #7) ──
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
PERMANENT_SESSION_LIFETIME = 8 * 3600

# ── Flag للتمييز بين وضع Admin و Company ──
IS_MASTER_INSTANCE = not COMPANY_ID
