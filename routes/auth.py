import hashlib
import time
import threading
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, current_app, make_response
from werkzeug.security import check_password_hash
from functools import wraps
from database import db
from models import User
from i18n import make_t, DEFAULT_LANG
import server_config

auth_bp = Blueprint("auth", __name__)

# ---------- حد محاولات الدخول (قفل مؤقت بعد محاولات خاطئة + تأخير) ----------
MAX_LOGIN_ATTEMPTS = 5      # عدد المحاولات الخاطئة المسموح بها قبل القفل
LOGIN_LOCK_SECONDS = 900    # مدة القفل المؤقت (15 دقيقة)
_LOGIN_FAILURES = {}        # development/Desktop fallback only
_cleanup_lock = threading.Lock()
_REDIS_CLIENT = None
_REDIS_UNAVAILABLE = False


def _redis_login_store():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _REDIS_UNAVAILABLE:
        return None
    env = str(os.environ.get("DYNAMICPRO_ENV", "")).lower()
    if env not in {"production", "prod"}:
        return None
    uri = os.environ.get("REDIS_URL") or os.environ.get("RATELIMIT_STORAGE_URI")
    if not uri:
        raise RuntimeError("Production login protection requires REDIS_URL or RATELIMIT_STORAGE_URI.")
    try:
        import redis
        _REDIS_CLIENT = redis.Redis.from_url(uri, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        _REDIS_CLIENT.ping()
        return _REDIS_CLIENT
    except Exception as exc:
        _REDIS_UNAVAILABLE = True
        raise RuntimeError("Production login protection cannot connect to Redis.") from exc


def _redis_key(prefix, key):
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"dynamicpro:login:{prefix}:{digest}"


def _cleanup_old_failures():
    """Remove expired lock entries every 10 minutes to prevent memory leak."""
    now = time.time()
    with _cleanup_lock:
        expired = [k for k, v in _LOGIN_FAILURES.items()
                   if v.get("lock_until", 0) < now and v.get("lock_until", 0) > 0]
        for k in expired:
            _LOGIN_FAILURES.pop(k, None)


# Schedule cleanup every 10 minutes
def _schedule_cleanup():
    try:
        t = threading.Timer(600, _schedule_cleanup)
        t.daemon = True
        t.start()
        _cleanup_old_failures()
    except Exception:
        pass

_schedule_cleanup()


def _login_key(username):
    """مفتاح للتتبّع: عنوان IP + اسم المستخدم (يمنع تخمين كلمة مرور لنفس الحساب)."""
    ip = request.remote_addr or "unknown"
    return f"{ip}:{str(username or '').lower()}"


def _check_login_lock(key):
    """Return remaining lock seconds, using Redis for production."""
    store = _redis_login_store()
    if store is not None:
        lock_key = _redis_key("lock", key)
        remaining = store.ttl(lock_key)
        return max(int(remaining), 0)
    rec = _LOGIN_FAILURES.get(key)
    if not rec:
        return 0
    lock_until = rec.get("lock_until") or 0
    remaining = int(lock_until - time.time())
    if remaining > 0:
        return remaining
    if lock_until:
        _LOGIN_FAILURES.pop(key, None)
    return 0


def _register_login_failure(key):
    """Register a failed login atomically in Redis for production."""
    store = _redis_login_store()
    if store is not None:
        count_key = _redis_key("count", key)
        count = store.incr(count_key)
        if count == 1:
            store.expire(count_key, LOGIN_LOCK_SECONDS)
        if count >= MAX_LOGIN_ATTEMPTS:
            store.set(_redis_key("lock", key), "1", ex=LOGIN_LOCK_SECONDS)
        if count >= 3:
            time.sleep(min(0.3 * (count - 2), 2.0))
        return
    rec = _LOGIN_FAILURES.setdefault(key, {"count": 0, "lock_until": 0})
    rec["count"] += 1
    if rec["count"] >= MAX_LOGIN_ATTEMPTS:
        rec["lock_until"] = time.time() + LOGIN_LOCK_SECONDS
    if rec["count"] >= 3:
        time.sleep(min(0.3 * (rec["count"] - 2), 2.0))


def _reset_login_failures(key):
    store = _redis_login_store()
    if store is not None:
        store.delete(_redis_key("count", key), _redis_key("lock", key))
        return
    _LOGIN_FAILURES.pop(key, None)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check standard employee login
        if "user_id" in session:
            return f(*args, **kwargs)
        # Check company user login (CRITICAL #4)
        try:
            from licensing.auth import is_company_user_logged_in, can_access as lic_can_access
            if is_company_user_logged_in():
                from licensing.models import LicCompanyUser, LicCompany
                from database import db as _db
                company_id = session.get("lic_company_id")
                if company_id:
                    from licensing.engine import can_access
                    access = can_access(company_id)
                    if not access["allowed"]:
                        return redirect(url_for("auth.login"))
                    return f(*args, **kwargs)
        except (ImportError, Exception):
            pass
        return redirect(url_for("auth.login"))
    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("pages.dashboard"))
        resp = make_response(render_template("login.html"))
        if not request.cookies.get("lang"):
            import utils.settings as settings_module
            default_lang = settings_module.get("default_lang", "ar")
            if default_lang not in ("ar", "en"):
                default_lang = "ar"
            resp.set_cookie("lang", default_lang, max_age=60 * 60 * 24 * 365)
        return resp

    # تسجيل دخول من الـ API
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    # كلمة مرور الوصول للخادم (إن كانت مفعّلة)
    access_password = data.get("access_password", "")
    required = current_app.config.get("SERVER_ACCESS_PASSWORD", "")
    if required and not server_config.check_access_password(required, access_password):
        lang = request.cookies.get("lang", DEFAULT_LANG)
        from auditlog import log_action
        log_action("login_failed", "server_access", None, "كلمة مرور وصول الخادم خاطئة")
        return jsonify({
            "success": False,
            "code": "bad_access",
            "message": make_t(lang)("login.badAccess"),
        }), 401

    # ── فحص: هل هذا مستخدم شركة (LicCompanyUser)؟ ──
    email_lower = (username or "").strip().lower()
    if "@" in email_lower:
        try:
            from licensing.models import LicCompanyUser
            cu = LicCompanyUser.query.filter_by(email=email_lower, is_active=True).first()
            if cu:
                from licensing.auth import authenticate_company_user, _check_lock as lic_check_lock
                lock_key = f"{request.remote_addr}:{email_lower}"
                if lic_check_lock(lock_key):
                    return jsonify({
                        "success": False, "code": "locked",
                        "message": "تم قفل محاولات الدخول مؤقتاً.",
                    }), 429
                result = authenticate_company_user(email_lower, password)
                if result.get("success"):
                    return jsonify(result)
                _register_login_failure(_login_key(username))
                return jsonify(result), 401
        except ImportError:
            pass

    # حد محاولات الدخول: قفل مؤقت بعد 5 محاولات خاطئة
    key = _login_key(username)
    lock_remaining = _check_login_lock(key)
    if lock_remaining:
        return jsonify({
            "success": False,
            "code": "locked",
            "message": "تم قفل محاولات الدخول مؤقتاً بسبب محاولات خاطئة متكررة. "
                       f"حاول مجدداً بعد {lock_remaining // 60} دقيقة.",
            "retry_after": lock_remaining,
        }), 429

    user = User.query.filter_by(username=username).first()
    if user and user.is_active and check_password_hash(user.password_hash, password):
        _reset_login_failures(key)
        # تدوير الجلسة: جلسة جديدة بالكامل بعد تسجيل الدخول (حماية من session fixation)
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["full_name"] = user.full_name
        session["role"] = user.role
        from auditlog import log_action
        log_action("login", "user", user.id, user.username)
        # Log license activity & notify owner
        try:
            from routes.license import log_license_activity, create_owner_notification
            log_license_activity("login", f"user={user.username}", user.id, user.username)
            if user.username != "admin":
                create_owner_notification(
                    title=f"دخول مستخدم: {user.username}",
                    message=f"المستخدم {user.full_name} ({user.username}) قام بتسجيل الدخول من {request.remote_addr}",
                    notif_type="login",
                    related_user=user.username,
                )
        except Exception as e:
            #	Log license activity/failure notification error (لا يمنع دخول المستخدم)
            from auditlog import log_action
            log_action("login_notif_error", "system", user.id, f"خطأ في تنبيه الدخول: {str(e)[:100]}")
        return jsonify({"success": True, "user": user.to_dict()})

    from auditlog import log_action
    log_action("login_failed", "user", getattr(user, "id", None), f"محاولة دخول خاطئة ({username})")
    _register_login_failure(key)
    if _check_login_lock(key):
        return jsonify({
            "success": False,
            "code": "locked",
            "message": "تم قفل محاولات الدخول مؤقتاً بسبب محاولات خاطئة متكررة. "
                       f"حاول مجدداً بعد {LOGIN_LOCK_SECONDS // 60} دقيقة.",
            "retry_after": LOGIN_LOCK_SECONDS,
        }), 429

    return jsonify({"success": False, "message": "بيانات الدخول غير صحيحة"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    from auditlog import log_action
    log_action("logout", "user", session.get("user_id"), session.get("username", ""))
    try:
        from licensing.auth import is_company_user_logged_in, logout_company_user
        if is_company_user_logged_in():
            logout_company_user()
            try:
                from licensing.auth import logout_master_user
                logout_master_user()
            except ImportError:
                pass
            return jsonify({"success": True})
    except ImportError:
        pass
    session.clear()
    return jsonify({"success": True})


@auth_bp.route("/api/me")
def me():
    try:
        from licensing.auth import is_company_user_logged_in, get_company_session_data
        if is_company_user_logged_in():
            data = get_company_session_data()
            return jsonify({"authenticated": True, "type": "company", **data})
    except ImportError:
        pass
    if "user_id" not in session:
        return jsonify({"authenticated": False}), 401
    user = db.session.get(User, session["user_id"])
    return jsonify({"authenticated": True, "type": "employee", "user": user.to_dict()})
