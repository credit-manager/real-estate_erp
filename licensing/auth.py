# -*- coding: utf-8 -*-
"""Company user authentication for DynamicPro ERP.

Flow:
    Email + Password
        ↓
    LicCompanyUser (master DB) → identify company
        ↓
    can_access() → subscription + license check
        ↓
    Company DB → authenticate user
        ↓
    Session (company_id, user_id, role, db_name)

Two login types exist:
    1. Master Login (/admin/login) → LicMasterUser → Admin Panel
    2. Company Login (/login) → Company User → Company DB

Browser authentication uses the revocable Flask session plus CSRF protection.
JWTs are not stored in the Flask cookie. Token issuance is reserved for explicit
API clients instead of silently placing access/refresh tokens in browser state.
"""
import logging
import time
from datetime import datetime

from flask import session, request
from sqlalchemy import text
from werkzeug.security import check_password_hash

from database import db
from licensing.models import LicCompany, LicCompanyUser, LicMasterUser
from licensing.engine import can_access
from licensing.db_manager import get_company_engine

log = logging.getLogger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 900
_LOGIN_FAILURES = {}


def _login_lock_key(email, ip=None):
    return f"{ip or request.remote_addr or 'unknown'}:{(email or '').lower()}"


def _check_lock(key):
    rec = _LOGIN_FAILURES.get(key)
    if not rec:
        return 0
    lock_until = rec.get("lock_until", 0)
    remaining = int(lock_until - time.time())
    if remaining > 0:
        return remaining
    if lock_until:
        _LOGIN_FAILURES.pop(key, None)
    return 0


def _register_failure(key):
    rec = _LOGIN_FAILURES.setdefault(key, {"count": 0, "lock_until": 0})
    rec["count"] += 1
    if rec["count"] >= MAX_LOGIN_ATTEMPTS:
        rec["lock_until"] = time.time() + LOGIN_LOCK_SECONDS
    if rec["count"] >= 3:
        time.sleep(min(0.3 * (rec["count"] - 2), 2.0))


def _reset_failures(key):
    _LOGIN_FAILURES.pop(key, None)


def _cleanup_old():
    import threading as _t
    now = time.time()
    expired = [k for k, v in _LOGIN_FAILURES.items()
               if 0 < v.get("lock_until", 0) < now]
    for k in expired:
        _LOGIN_FAILURES.pop(k, None)
    timer = _t.Timer(600, _cleanup_old)
    timer.daemon = True
    timer.start()


try:
    _cleanup_old()
except Exception:
    pass


SESS_COMPANY_ID = "lic_company_id"
SESS_COMPANY_USER_ID = "lic_company_user_id"
SESS_COMPANY_NAME = "lic_company_name"
SESS_COMPANY_DB_NAME = "lic_company_db_name"
SESS_COMPANY_ROLE = "lic_company_role"
SESS_COMPANY_USER_EMAIL = "lic_company_user_email"
SESS_COMPANY_FULL_NAME = "lic_company_full_name"

SESS_MASTER_USER_ID = "master_user_id"
SESS_MASTER_EMAIL = "master_user_email"
SESS_MASTER_NAME = "master_user_name"
SESS_MASTER_ROLE = "master_user_role"
SESS_MASTER_JTI = "master_jti"

COMPANY_SESSION_KEYS = [
    SESS_COMPANY_ID, SESS_COMPANY_USER_ID, SESS_COMPANY_NAME,
    SESS_COMPANY_DB_NAME, SESS_COMPANY_ROLE, SESS_COMPANY_USER_EMAIL,
    SESS_COMPANY_FULL_NAME,
]
MASTER_SESSION_KEYS = [
    SESS_MASTER_USER_ID, SESS_MASTER_EMAIL, SESS_MASTER_NAME,
    SESS_MASTER_ROLE, SESS_MASTER_JTI,
]


def clear_company_session():
    for key in COMPANY_SESSION_KEYS:
        session.pop(key, None)


def clear_master_session():
    for key in MASTER_SESSION_KEYS:
        session.pop(key, None)


def authenticate_company_user(email, password):
    email = (email or "").strip().lower()
    password = (password or "").strip()

    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}

    cu = LicCompanyUser.query.filter_by(email=email, is_active=True).first()
    if not cu:
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    if not check_password_hash(cu.password_hash, password):
        log.warning("Failed login for company user %s (company %d)", email, cu.company_id)
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    company = db.session.get(LicCompany, cu.company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    if company.status != "active":
        status_msg = "تم تعليق حساب الشركة" if company.status == "suspended" else "حساب الشركة غير نشط"
        return {"success": False, "message": status_msg}

    access = can_access(company.id)
    if not access["allowed"]:
        warning = access.get("warning") or "الوصول غير مسموح"
        return {"success": False, "message": warning, "access": access}

    user_role = cu.role
    user_full_name = cu.full_name or email
    company_db_user_id = None

    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, username, email, full_name, role, is_active "
                     "FROM users WHERE email = :email AND is_active = true"),
                {"email": email},
            )
            row = result.fetchone()
            if row:
                company_db_user_id = row[0]
                user_role = row[4] or cu.role
                user_full_name = row[3] or cu.full_name or email
    except Exception as e:
        log.info("Company DB unavailable for %s, using master DB auth: %s", email, e)

    cu.last_login = datetime.utcnow()
    db.session.commit()

    session.permanent = True
    session.clear()
    session[SESS_COMPANY_ID] = company.id
    session[SESS_COMPANY_USER_ID] = company_db_user_id or cu.id
    session[SESS_COMPANY_NAME] = company.name_ar or company.name
    session[SESS_COMPANY_DB_NAME] = company.db_name
    session[SESS_COMPANY_ROLE] = user_role
    session[SESS_COMPANY_USER_EMAIL] = email
    session[SESS_COMPANY_FULL_NAME] = user_full_name

    log.info("Company user logged in: %s (company=%d, role=%s)", email, company.id, user_role)

    return {
        "success": True,
        "message": f"مرحباً {session[SESS_COMPANY_FULL_NAME]}",
        "company": {
            "id": company.id,
            "name": company.name_ar or company.name,
            "db_name": company.db_name,
        },
        "user": {
            "id": company_db_user_id or cu.id,
            "email": email,
            "full_name": user_full_name,
            "role": user_role,
        },
        "access": access,
    }


def logout_company_user():
    email = session.get(SESS_COMPANY_USER_EMAIL, "")
    company_id = session.get(SESS_COMPANY_ID)
    log.info("Company user logged out: %s (company=%s)", email, company_id)
    clear_company_session()


def authenticate_master_user(email, password):
    """Authenticate platform admin using a revocable browser session only."""
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}

    user = LicMasterUser.query.filter_by(email=email).first()
    if not user or not user.is_active:
        try:
            from security.security_events import record_event
            record_event(
                "login_failure", master_user_email=email,
                ip=getattr(request, "remote_addr", None),
                user_agent=request.user_agent.string if request.user_agent else None,
                details={"reason": "user_not_found_or_inactive"}, severity="warning",
            )
        except Exception:
            pass
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    if not check_password_hash(user.password_hash, password):
        log.warning("Failed platform-admin login: %s", email)
        try:
            from security.security_events import record_event
            record_event(
                "login_failure", master_user_id=user.id, master_user_email=email,
                ip=getattr(request, "remote_addr", None),
                details={"reason": "wrong_password"}, severity="warning",
            )
        except Exception:
            pass
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    try:
        from security.security_events import record_event
        record_event(
            "login_success", master_user_id=user.id, master_user_email=email,
            ip=getattr(request, "remote_addr", None),
            details={"role": user.role}, severity="info",
        )
    except Exception:
        pass

    user.last_login = datetime.utcnow()
    clear_company_session()
    session.permanent = True
    session.clear()
    session[SESS_MASTER_USER_ID] = user.id
    session[SESS_MASTER_EMAIL] = user.email
    session[SESS_MASTER_NAME] = user.full_name or user.email
    session[SESS_MASTER_ROLE] = user.role

    # Keep the browser session revocable without putting JWT material into the cookie.
    jti = _start_master_session(user, is_company_user=False, extra=None)
    if jti:
        session[SESS_MASTER_JTI] = jti

    try:
        from security.rbac import ensure_user_role_link
        ensure_user_role_link(user.id, user.role)
    except Exception:
        pass

    db.session.commit()

    log.info("Platform admin logged in: %s (role=%s)", email, user.role)
    return {
        "success": True,
        "user": user.to_dict(),
        "mfa_enabled": _mfa_enabled_for(user.id),
    }


def logout_master_user():
    email = session.get(SESS_MASTER_EMAIL, "")
    log.info("Platform admin logged out: %s", email)
    _end_master_session()
    clear_master_session()


def _start_master_session(user, is_company_user=False, extra=None):
    """Create a revocable MasterSession without embedding JWTs in browser state."""
    try:
        import uuid
        from datetime import timedelta
        from security.models import MasterSession

        jti = uuid.uuid4().hex
        sess = MasterSession(
            master_user_id=user.id,
            jti=jti,
            refresh_token_hash=None,
            ip=request.remote_addr,
            user_agent=(request.user_agent.string[:250] if request.user_agent else None),
            expires_at=datetime.utcnow() + timedelta(days=7),
            last_seen=datetime.utcnow(),
        )
        db.session.add(sess)
        log.info("Revocable master session started for user %s", user.email)
        return jti
    except Exception as exc:
        log.error("Could not start master session for %s: %s", user.email, exc)
        return None


def _end_master_session():
    jti = session.get(SESS_MASTER_JTI)
    if not jti:
        return
    try:
        from security.models import MasterSession
        ms = MasterSession.query.filter_by(jti=jti, revoked=False).first()
        if ms:
            ms.revoked = True
            db.session.commit()
    except Exception as exc:
        log.error("Could not revoke master session %s: %s", jti, exc)


def _mfa_enabled_for(master_user_id):
    try:
        from security.two_factor import is_enabled
        return is_enabled(master_user_id)
    except Exception:
        return False


def get_master_session_data():
    """Return active master identity only when the persisted session is valid."""
    uid = session.get(SESS_MASTER_USER_ID)
    jti = session.get(SESS_MASTER_JTI)
    if not uid:
        return None
    try:
        from security.models import MasterSession
        from security.models import MasterSession
        from datetime import datetime
        master_session = MasterSession.query.filter_by(
            master_user_id=uid, jti=jti, revoked=False
        ).first() if jti else None
        if jti and (
            not master_session
            or (master_session.expires_at and master_session.expires_at < datetime.utcnow())
        ):
            clear_master_session()
            return None
        user = db.session.get(LicMasterUser, uid)
        if not user or not user.is_active:
            clear_master_session()
            return None
        if master_session:
            master_session.last_seen = datetime.utcnow()
            db.session.commit()
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name or user.email,
            "role": user.role,
        }
    except Exception:
        return None


def is_master_logged_in():
    return get_master_session_data() is not None


def get_company_session_data():
    company_id = session.get(SESS_COMPANY_ID)
    if not company_id:
        return None
    return {
        "company_id": company_id,
        "user_id": session.get(SESS_COMPANY_USER_ID),
        "company_name": session.get(SESS_COMPANY_NAME),
        "db_name": session.get(SESS_COMPANY_DB_NAME),
        "role": session.get(SESS_COMPANY_ROLE),
        "email": session.get(SESS_COMPANY_USER_EMAIL),
        "full_name": session.get(SESS_COMPANY_FULL_NAME),
    }


def is_company_user_logged_in():
    return bool(session.get(SESS_COMPANY_ID) and session.get(SESS_COMPANY_USER_ID))
