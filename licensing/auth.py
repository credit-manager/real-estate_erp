# -*- coding: utf-8 -*-
"""Company and Control Center authentication for DynamicPro ERP.

Browser authentication uses revocable Flask sessions plus CSRF protection.
Master users who require MFA never receive an authenticated master session after
password verification alone; they receive a narrowly scoped pending-MFA session
that can be used only for enrollment or verification.
"""
import logging
import time
from datetime import datetime, timedelta

from flask import request, session
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


def _check_lock(key):
    rec = _LOGIN_FAILURES.get(key)
    if not rec:
        return 0
    lock_until = rec.get("lock_until", 0)
    remaining = int(lock_until - time.time())
    if remaining > 0:
        return remaining
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
    import threading
    now = time.time()
    for key, value in list(_LOGIN_FAILURES.items()):
        lock_until = value.get("lock_until", 0)
        if 0 < lock_until < now:
            _LOGIN_FAILURES.pop(key, None)
    timer = threading.Timer(600, _cleanup_old)
    timer.daemon = True
    timer.start()


try:
    _cleanup_old()
except Exception:
    log.exception("Unable to start login-failure cleanup timer")

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
SESS_MASTER_MFA_PENDING = "master_mfa_pending"
SESS_MASTER_MFA_ISSUED_AT = "master_mfa_issued_at"

COMPANY_SESSION_KEYS = [
    SESS_COMPANY_ID, SESS_COMPANY_USER_ID, SESS_COMPANY_NAME,
    SESS_COMPANY_DB_NAME, SESS_COMPANY_ROLE, SESS_COMPANY_USER_EMAIL,
    SESS_COMPANY_FULL_NAME,
]
MASTER_SESSION_KEYS = [
    SESS_MASTER_USER_ID, SESS_MASTER_EMAIL, SESS_MASTER_NAME,
    SESS_MASTER_ROLE, SESS_MASTER_JTI,
]
PENDING_MFA_KEYS = [SESS_MASTER_USER_ID, SESS_MASTER_EMAIL, SESS_MASTER_MFA_PENDING, SESS_MASTER_MFA_ISSUED_AT]
MFA_PENDING_TTL_SECONDS = 300
MFA_PENDING_PATHS = {"/admin/security/2fa/enroll", "/admin/security/2fa/verify"}


def clear_company_session():
    for key in COMPANY_SESSION_KEYS:
        session.pop(key, None)


def clear_master_session():
    for key in MASTER_SESSION_KEYS:
        session.pop(key, None)


def clear_pending_mfa_session():
    for key in PENDING_MFA_KEYS:
        session.pop(key, None)


def is_pending_mfa_session():
    if not session.get(SESS_MASTER_MFA_PENDING):
        return False
    issued_at = session.get(SESS_MASTER_MFA_ISSUED_AT, 0)
    try:
        valid = (time.time() - float(issued_at)) <= MFA_PENDING_TTL_SECONDS
    except (TypeError, ValueError):
        valid = False
    if not valid:
        clear_pending_mfa_session()
        return False
    return True


def pending_mfa_user_id():
    return session.get(SESS_MASTER_USER_ID) if is_pending_mfa_session() else None


def _mfa_required(user_id):
    user = db.session.get(LicMasterUser, user_id)
    if user and str(user.role or "").strip().lower() == "super_admin":
        return True
    try:
        from security.two_factor import require_two_factor
        return not require_two_factor(user_id)
    except Exception:
        return False


def _mfa_enabled(user_id):
    try:
        from security.two_factor import is_enabled
        return is_enabled(user_id)
    except Exception:
        return False


def _establish_master_session(user):
    clear_pending_mfa_session()
    clear_company_session()
    session.permanent = True
    session.clear()
    session[SESS_MASTER_USER_ID] = user.id
    session[SESS_MASTER_EMAIL] = user.email
    session[SESS_MASTER_NAME] = user.full_name or user.email
    session[SESS_MASTER_ROLE] = user.role
    jti = _start_master_session(user)
    if not jti:
        session.clear()
        raise RuntimeError("Unable to create revocable master session")
    session[SESS_MASTER_JTI] = jti


def complete_pending_master_mfa(user_id):
    """Upgrade a valid pending-MFA session to a full revocable master session."""
    if not is_pending_mfa_session() or session.get(SESS_MASTER_USER_ID) != user_id:
        return False
    user = db.session.get(LicMasterUser, user_id)
    if not user or not user.is_active:
        clear_pending_mfa_session()
        return False
    try:
        _establish_master_session(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        session.clear()
        return False
    return True


def authenticate_company_user(email, password):
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}
    cu = LicCompanyUser.query.filter_by(email=email, is_active=True).first()
    if not cu or not check_password_hash(cu.password_hash, password):
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}
    company = db.session.get(LicCompany, cu.company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}
    if company.status != "active":
        message = "تم تعليق حساب الشركة" if company.status == "suspended" else "حساب الشركة غير نشط"
        return {"success": False, "message": message}
    access = can_access(company.id)
    if not access["allowed"]:
        return {"success": False, "message": access.get("warning") or "الوصول غير مسموح", "access": access}
    user_role = cu.role
    user_full_name = cu.full_name or email
    company_db_user_id = None
    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, username, email, full_name, role, is_active FROM users WHERE email = :email AND is_active = true"),
                {"email": email},
            ).fetchone()
            if row:
                company_db_user_id = row[0]
                user_role = row[4] or cu.role
                user_full_name = row[3] or cu.full_name or email
    except Exception as exc:
        log.info("Company DB unavailable for %s, using master DB auth: %s", email, exc)
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
    return {
        "success": True,
        "message": f"مرحباً {user_full_name}",
        "company": {"id": company.id, "name": company.name_ar or company.name, "db_name": company.db_name},
        "user": {"id": company_db_user_id or cu.id, "email": email, "full_name": user_full_name, "role": user_role},
        "access": access,
    }


def logout_company_user():
    clear_company_session()


def authenticate_master_user(email, password):
    """Verify password and create either a pending-MFA session or full session."""
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}
    user = LicMasterUser.query.filter_by(email=email).first()
    if not user or not user.is_active or not check_password_hash(user.password_hash, password):
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    try:
        from security.security_events import record_event
        record_event("login_success", master_user_id=user.id, master_user_email=email, ip=getattr(request, "remote_addr", None), details={"role": user.role}, severity="info")
    except Exception:
        log.exception("Unable to record master login event")

    if _mfa_required(user.id) or _mfa_enabled(user.id):
        clear_company_session()
        clear_master_session()
        session.clear()
        session.permanent = True
        session[SESS_MASTER_USER_ID] = user.id
        session[SESS_MASTER_EMAIL] = user.email
        session[SESS_MASTER_MFA_PENDING] = True
        session[SESS_MASTER_MFA_ISSUED_AT] = time.time()
        db.session.commit()
        enabled = _mfa_enabled(user.id)
        return {
            "success": False,
            "requires_2fa": True,
            "two_factor_required": True,
            "mfa_setup_required": not enabled,
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name or user.email, "role": user.role},
            "message": "مطلوب التحقق بالمصادقة الثنائية" if enabled else "يجب إعداد المصادقة الثنائية لهذا الحساب",
        }

    user.last_login = datetime.utcnow()
    _establish_master_session(user)
    try:
        from security.rbac import ensure_user_role_link
        ensure_user_role_link(user.id, user.role)
    except Exception:
        log.exception("Unable to ensure master role link")
    db.session.commit()
    return {"success": True, "user": user.to_dict(), "mfa_enabled": False}


def logout_master_user():
    _end_master_session()
    clear_master_session()
    clear_pending_mfa_session()


def _start_master_session(user, is_company_user=False, extra=None):
    from security.models import MasterSession
    jti = __import__("uuid").uuid4().hex
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
    return jti


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
    except Exception:
        log.exception("Unable to revoke master session %s", jti)


def get_master_session_data():
    """Return an authenticated master identity only after MFA when required."""
    uid = session.get(SESS_MASTER_USER_ID)
    if not uid:
        return None
    if is_pending_mfa_session():
        if request.path in MFA_PENDING_PATHS:
            user = db.session.get(LicMasterUser, uid)
            if user and user.is_active:
                return {"id": user.id, "email": user.email, "full_name": user.full_name or user.email, "role": user.role, "mfa_pending": True}
        return None
    jti = session.get(SESS_MASTER_JTI)
    try:
        from security.models import MasterSession
        master_session = MasterSession.query.filter_by(master_user_id=uid, jti=jti, revoked=False).first() if jti else None
        if not jti or not master_session or (master_session.expires_at and master_session.expires_at < datetime.utcnow()):
            clear_master_session()
            return None
        user = db.session.get(LicMasterUser, uid)
        if not user or not user.is_active:
            clear_master_session()
            return None
        master_session.last_seen = datetime.utcnow()
        db.session.commit()
        return {"id": user.id, "email": user.email, "full_name": user.full_name or user.email, "role": user.role}
    except Exception:
        return None


def is_master_logged_in():
    return get_master_session_data() is not None


def get_company_session_data():
    company_id = session.get(SESS_COMPANY_ID)
    if not company_id:
        return None
    return {"company_id": company_id, "user_id": session.get(SESS_COMPANY_USER_ID), "company_name": session.get(SESS_COMPANY_NAME), "db_name": session.get(SESS_COMPANY_DB_NAME), "role": session.get(SESS_COMPANY_ROLE), "email": session.get(SESS_COMPANY_USER_EMAIL), "full_name": session.get(SESS_COMPANY_FULL_NAME)}


def is_company_user_logged_in():
    return bool(session.get(SESS_COMPANY_ID) and session.get(SESS_COMPANY_USER_ID))
