"""Role-based access control (RBAC) for Dynamic Pro ERP.

Modules are the sections of the application; actions are view/create/edit/delete.
The "admin" role has full access. Every other role reads its permissions from
the Role table. Missing/unknown roles fail closed and receive no permissions.
Session-based employee access is also revalidated against the active User row.
"""
from functools import wraps
from flask import session, redirect, url_for, jsonify

MODULES = [
    "dashboard",
    "projects",
    "sales",
    "procurement",
    "inventory",
    "manufacturing",
    "finance",
    "accounting",
    "hr",
    "payroll",
    "realestate",
    "rentals",
    "crm",
    "reports",
    "audit",
    "backup",
    "users",
    "roles",
    "settings",
    "companies",
    "financial_years",
    "currencies",
    "taxes",
    "workflow",
]

ACTIONS = ["view", "create", "edit", "delete"]

ADMIN_MODULES = [
    "audit", "backup", "users", "roles", "settings", "companies",
    "financial_years", "currencies", "taxes",
]

MODULE_LABELS = {
    "dashboard": "dashboard",
    "projects": "projects",
    "sales": "sales",
    "procurement": "procurement",
    "inventory": "inventory",
    "manufacturing": "manufacturing",
    "finance": "finance",
    "accounting": "accounting",
    "hr": "hr",
    "payroll": "payroll",
    "realestate": "realestate",
    "rentals": "rentals",
    "crm": "crm",
    "reports": "reports",
    "audit": "audit",
    "backup": "backup",
    "users": "users",
    "roles": "roles",
    "settings": "settings",
    "companies": "companies",
    "financial_years": "financial_years",
    "currencies": "currencies",
    "taxes": "taxes",
    "workflow": "workflow",
}


def _all_true():
    return {m: {a: True for a in ACTIONS} for m in MODULES}


def _all_false():
    return {m: {a: False for a in ACTIONS} for m in MODULES}


def _view_only():
    p = _all_false()
    for m in MODULES:
        p[m]["view"] = True
    for m in ADMIN_MODULES:
        p[m]["view"] = False
    return p


def _normalize(raw):
    p = _all_false()
    for m, actions in (raw or {}).items():
        if m not in p:
            continue
        for a, v in (actions or {}).items():
            if a in p[m]:
                p[m][a] = bool(v)
    return p


def all_true():
    return _all_true()


def view_only():
    return _view_only()


def get_role_permissions(role_name):
    """Return normalized permissions for a role; unknown roles fail closed."""
    if role_name == "admin":
        return _all_true()
    if not role_name:
        return _all_false()
    from models import Role
    role = Role.query.filter_by(name=role_name).first()
    if role and role.permissions:
        return _normalize(role.permissions)
    return _all_false()


def user_can(role_name, module, action):
    if module not in MODULES or action not in ACTIONS:
        return False
    return get_role_permissions(role_name)[module][action]


def session_role():
    return session.get("role", "")


def _employee_session_valid():
    """Revalidate the employee session against the current active User record."""
    user_id = session.get("user_id")
    if not user_id:
        return False
    try:
        from database import db
        from models import User
        user = db.session.get(User, user_id)
        if user is None or not user.is_active:
            session.clear()
            return False
        # Do not trust mutable privilege data stored in the cookie/session.
        session["role"] = user.role
        session["username"] = user.username
        session["full_name"] = user.full_name
        return True
    except Exception:
        # Authorization must fail closed if the identity source cannot be read.
        return False


def can(module, action):
    """Template/route helper using the currently authenticated user's role."""
    if not _employee_session_valid():
        return False
    return user_can(session_role(), module, action)


def current_perms():
    """{module: [allowed actions]} for the currently authenticated employee."""
    if not _employee_session_valid():
        return {m: [] for m in MODULES}
    role = session_role()
    p = _all_true() if role == "admin" else get_role_permissions(role)
    return {m: [a for a in ACTIONS if p[m][a]] for m in MODULES}


def require_page(module, action="view"):
    """Decorator for page routes. Shows a 403 page when access is denied."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not _employee_session_valid():
                return redirect(url_for("auth.login"))
            if not user_can(session_role(), module, action):
                return redirect(url_for("pages.permission_denied"))
            return f(*args, **kwargs)
        return wrapper
    return deco


def require_api(module, action):
    """Decorator for API routes. Returns 403 JSON when access is denied."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not _employee_session_valid():
                return jsonify({"message": "غير مسجل الدخول"}), 401
            if not user_can(session_role(), module, action):
                return jsonify({
                    "message": "لا تملك صلاحية لهذا الإجراء",
                    "error_key": "permissions.denied",
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return deco


def require_api_any(action, modules):
    """Decorator for API routes shared across modules."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not _employee_session_valid():
                return jsonify({"message": "غير مسجل الدخول"}), 401
            if not any(user_can(session_role(), m, action) for m in modules):
                return jsonify({
                    "message": "لا تملك صلاحية لهذا الإجراء",
                    "error_key": "permissions.denied",
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return deco


def require_any_view(f):
    """Decorator for API routes that may be used by any role with any view."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _employee_session_valid():
            return jsonify({"message": "غير مسجل الدخول"}), 401
        perms = current_perms()
        if not any(perms[m] for m in perms):
            return jsonify({
                "message": "لا تملك صلاحية لعرض أي وحدة",
                "error_key": "permissions.denied",
            }), 403
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Decorator for page routes: admins only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _employee_session_valid():
            return redirect(url_for("auth.login"))
        if session_role() != "admin":
            return redirect(url_for("pages.dashboard"))
        return f(*args, **kwargs)
    return decorated
