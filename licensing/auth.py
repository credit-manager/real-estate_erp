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

# ── Rate Limiting ───────────────────────────────────────────

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
    time.sleep(0.3)


def _reset_failures(key):
    _LOGIN_FAILURES.pop(key, None)


# ── Session Keys ────────────────────────────────────────────

SESS_COMPANY_ID = "lic_company_id"
SESS_COMPANY_USER_ID = "lic_company_user_id"
SESS_COMPANY_NAME = "lic_company_name"
SESS_COMPANY_DB_NAME = "lic_company_db_name"
SESS_COMPANY_ROLE = "lic_company_role"
SESS_COMPANY_USER_EMAIL = "lic_company_user_email"
SESS_COMPANY_FULL_NAME = "lic_company_full_name"

# Platform Admin (Master) keys — fully separated from company-user session.
SESS_MASTER_USER_ID = "master_user_id"
SESS_MASTER_EMAIL = "master_user_email"
SESS_MASTER_NAME = "master_user_name"
SESS_MASTER_ROLE = "master_user_role"

COMPANY_SESSION_KEYS = [
    SESS_COMPANY_ID, SESS_COMPANY_USER_ID, SESS_COMPANY_NAME,
    SESS_COMPANY_DB_NAME, SESS_COMPANY_ROLE, SESS_COMPANY_USER_EMAIL,
    SESS_COMPANY_FULL_NAME,
]
MASTER_SESSION_KEYS = [
    SESS_MASTER_USER_ID, SESS_MASTER_EMAIL, SESS_MASTER_NAME, SESS_MASTER_ROLE,
]


def clear_company_session():
    """Remove all company-user session keys (used when entering admin context)."""
    for key in COMPANY_SESSION_KEYS:
        session.pop(key, None)


def clear_master_session():
    """Remove all platform-admin session keys (used when entering company context)."""
    for key in MASTER_SESSION_KEYS:
        session.pop(key, None)


# ── Core Login Logic ────────────────────────────────────────

def authenticate_company_user(email, password):
    """Authenticate a company user.

    Auth flow:
    1. Find LicCompanyUser in master DB → identify company
    2. Verify password against master DB record
    3. Check subscription + license
    4. (Optional) Verify user exists in company DB
    5. Create session

    When company DB is unavailable (e.g. no CREATEDB privilege),
    authentication falls back to master DB only.

    Returns:
        dict: {success, message, company?, user?, access?}
    """
    email = (email or "").strip().lower()
    password = (password or "").strip()

    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}

    # Step 1: Find user in master DB
    cu = LicCompanyUser.query.filter_by(email=email, is_active=True).first()
    if not cu:
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    # Step 2: Verify password against master DB record
    if not check_password_hash(cu.password_hash, password):
        log.warning("Failed login for company user %s (company %d)", email, cu.company_id)
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    # Step 3: Get company
    company = db.session.get(LicCompany, cu.company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    if company.status != "active":
        status_msg = "تم تعليق حساب الشركة" if company.status == "suspended" else "حساب الشركة غير نشط"
        return {"success": False, "message": status_msg}

    # Step 4: Check subscription + license
    access = can_access(company.id)
    if not access["allowed"]:
        warning = access.get("warning") or "الوصول غير مسموح"
        return {"success": False, "message": warning, "access": access}

    # Step 5: Try to verify against company DB (optional — don't fail if DB unavailable)
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

    # Step 6: Update last_login in master DB
    cu.last_login = datetime.utcnow()
    db.session.commit()

    # Step 7: Store in session (mutual exclusion with platform-admin session)
    session.permanent = True
    clear_master_session()  # a client can never hold admin panel access
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
    """Clear company user session."""
    email = session.get(SESS_COMPANY_USER_EMAIL, "")
    company_id = session.get(SESS_COMPANY_ID)
    log.info("Company user logged out: %s (company=%s)", email, company_id)
    clear_company_session()


# ── Platform Admin (Master) Auth ─────────────────────────────

def authenticate_master_user(email, password):
    """Authenticate a Platform Admin (LicMasterUser) for the Admin Panel.

    Fully separate from company-user auth: it only sets master session keys,
    and always clears any leftover company-user session first, so a client
    account can never sit inside the platform admin panel.
    """
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        return {"success": False, "message": "البريد الإلكتروني وكلمة المرور مطلوبان"}

    user = LicMasterUser.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    if not check_password_hash(user.password_hash, password):
        log.warning("Failed platform-admin login: %s", email)
        return {"success": False, "message": "بيانات الدخول غير صحيحة"}

    user.last_login = datetime.utcnow()
    clear_company_session()  # mutual exclusion: a client session can't enter admin
    session.permanent = True
    session[SESS_MASTER_USER_ID] = user.id
    session[SESS_MASTER_EMAIL] = user.email
    session[SESS_MASTER_NAME] = user.full_name or user.email
    session[SESS_MASTER_ROLE] = user.role
    db.session.commit()

    log.info("Platform admin logged in: %s (role=%s)", email, user.role)
    return {"success": True, "user": user.to_dict()}


def logout_master_user():
    """Clear platform-admin session keys only."""
    email = session.get(SESS_MASTER_EMAIL, "")
    log.info("Platform admin logged out: %s", email)
    clear_master_session()


def get_master_session_data():
    """Get current platform-admin info from session. None if not logged in."""
    uid = session.get(SESS_MASTER_USER_ID)
    if not uid:
        return None
    return {
        "id": uid,
        "email": session.get(SESS_MASTER_EMAIL),
        "full_name": session.get(SESS_MASTER_NAME),
        "role": session.get(SESS_MASTER_ROLE),
    }


def is_master_logged_in():
    """Check if a platform admin is currently logged in."""
    return SESS_MASTER_USER_ID in session


# ── Session Helpers ─────────────────────────────────────────

def get_company_session_data():
    """Get current company user info from session. Returns None if not logged in."""
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
    """Check if a company user is currently logged in."""
    return SESS_COMPANY_ID in session


# ── Access Middleware ────────────────────────────────────────

def company_login_required(f):
    """Decorator: require company user login + valid subscription/license.

    Redirects to /login if not authenticated.
    Returns 403 if subscription/license expired.
    """
    from functools import wraps
    from flask import redirect, url_for, jsonify, request

    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_company_user_logged_in():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "غير مصرح"}), 401
            return redirect(url_for("company_auth.company_login"))

        company_id = session.get(SESS_COMPANY_ID)
        access = can_access(company_id)
        if not access["allowed"]:
            logout_company_user()
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "message": access.get("warning") or "الوصول غير مسموح",
                    "code": "access_denied",
                }), 403
            return redirect(url_for("company_auth.company_login"))

        return f(*args, **kwargs)

    return decorated


def master_login_required(f):
    """Decorator: require platform-admin login.

    Returns 401 JSON for /api/ paths, otherwise redirects to the admin panel.
    """
    from functools import wraps
    from flask import redirect, url_for, jsonify

    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_master_logged_in():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "غير مصرح"}), 401
            return redirect(url_for("admin_lic.admin_panel"))
        return f(*args, **kwargs)

    return decorated


def get_company_engine_from_session():
    """Get a SQLAlchemy engine for the current company's DB.

    Returns None if no company is in session or company not found.
    """
    company_id = session.get(SESS_COMPANY_ID)
    if not company_id:
        return None
    from database import db as _db
    company = _db.session.get(LicCompany, company_id)
    if not company:
        return None
    return get_company_engine(company)


def get_company_db_connection():
    """Get a raw connection to the current company's DB.

    Returns (connection, engine) or (None, None) on failure.
    Caller must close connection and dispose engine.
    """
    engine = get_company_engine_from_session()
    if not engine:
        return None, None
    try:
        conn = engine.connect()
        return conn, engine
    except Exception as e:
        log.error("Failed to connect to company DB: %s", e)
        engine.dispose()
        return None, None
