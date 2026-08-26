import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# إعداد قاعدة البيانات
DB_USER = os.environ.get("DB_USER", "mokawlat_user")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "dynamicpro")

# كلمة مرور قاعدة البيانات: لا توجد قيمة افتراضية مكتوبة في الكود (أمان).
# تُقرأ من متغير البيئة DB_PASSWORD أولاً، ثم من ملف محلي محمي (.db_password)،
# وإلا تُولَّد كلمة مرور عشوائية قوية وتُحفظ في الملف المحلي.
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
        print("[config] تم توليد كلمة مرور قاعدة البيانات وحفظها في .db_password "
              "(اضبط متغير DB_PASSWORD لتطابق قاعدة البيانات الفعلية).")
    except OSError:
        pass

SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# مفتاح التشفير للجلسات
# يُنشأ تلقائياً ويُحفظ في ملف محلي (لا يُستخدم مفتاح ثابت في الكود)
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
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass

# عدم الكاش للملفات الثابتة: أي تعديل على JS/CSS يظهر فوراً دون كاش قديم
SEND_FILE_MAX_AGE_DEFAULT = 0

# أمان الجلسات (cookies)
SESSION_COOKIE_HTTPONLY = True        # يمنع قراءة الكوكي عبر JavaScript (XSS)
SESSION_COOKIE_SAMESITE = "Lax"       # يمنع إرسال الكوكي في طلبات مواقع أخرى (CSRF)
SESSION_COOKIE_SECURE = False         # يُفعَّل تلقائياً في وضع الإنتاج مع HTTPS
PERMANENT_SESSION_LIFETIME = 8 * 3600  # انتهاء الجلسة بعد 8 ساعات
