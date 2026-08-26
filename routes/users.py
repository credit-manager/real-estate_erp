from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from models import User, AuditLog
from routes.auth import login_required
from permissions import require_api

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("", methods=["GET"])
@require_api("users", "view")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users])


@users_bp.route("", methods=["POST"])
@require_api("users", "create")
def create_user():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username:
        return jsonify({"message": "اسم المستخدم مطلوب", "error_key": "users.usernameRequired"}), 400
    if not full_name:
        return jsonify({"message": "الاسم الكامل مطلوب", "error_key": "users.fullNameRequired"}), 400
    if not password:
        return jsonify({"message": "كلمة المرور مطلوبة", "error_key": "users.passwordRequired"}), 400
    if (len(password) < 8
            or not any(c.isalpha() for c in password)
            or not any(c.isdigit() for c in password)):
        return jsonify({
            "message": "كلمة المرور يجب ألا تقل عن 8 أحرف وتحتوي على حروف وأرقام",
            "error_key": "profile.passwordWeak",
        }), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "اسم المستخدم مستخدم بالفعل", "error_key": "users.usernameExists"}), 409
    if email and User.query.filter_by(email=email).first():
        return jsonify({"message": "البريد الإلكتروني مستخدم بالفعل", "error_key": "users.emailExists"}), 409

    user = User(
        username=username,
        full_name=full_name,
        email=email or f"{username}@mokawlat.local",
        role=data.get("role") or "employee",
        is_active=bool(data.get("is_active", True)),
        password_hash=generate_password_hash(password),
    )
    db_session_add(user)
    from auditlog import log_action
    log_action("create", "user", user.id, username)
    return jsonify(user.to_dict()), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
@require_api("users", "edit")
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    # Owner protection
    if user.username == "admin" and user.role == "admin":
        return jsonify({"message": "لا يمكن تعديل حساب المالك", "error_key": "users.ownerProtected"}), 403
    data = request.get_json() or {}

    username = (data.get("username") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()

    if not username:
        return jsonify({"message": "اسم المستخدم مطلوب", "error_key": "users.usernameRequired"}), 400
    if not full_name:
        return jsonify({"message": "الاسم الكامل مطلوب", "error_key": "users.fullNameRequired"}), 400

    conflict = User.query.filter(User.username == username, User.id != user.id).first()
    if conflict:
        return jsonify({"message": "اسم المستخدم مستخدم بالفعل", "error_key": "users.usernameExists"}), 409
    conflict = User.query.filter(User.email == email, User.id != user.id).first()
    if email and conflict:
        return jsonify({"message": "البريد الإلكتروني مستخدم بالفعل", "error_key": "users.emailExists"}), 409

    user.username = username
    user.full_name = full_name
    user.email = email or user.email
    if "role" in data:
        # Prevent changing owner's role
        if user.username == "admin" and user.role == "admin":
            return jsonify({"message": "لا يمكن تغيير صلاحيات المالك", "error_key": "users.ownerProtected"}), 403
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    password = data.get("password") or ""
    if password:
        if (len(password) < 8
                or not any(c.isalpha() for c in password)
                or not any(c.isdigit() for c in password)):
            return jsonify({
                "message": "كلمة المرور يجب ألا تقل عن 8 أحرف وتحتوي على حروف وأرقام",
                "error_key": "profile.passwordWeak",
            }), 400
        user.password_hash = generate_password_hash(password)

    if user.id == session.get("user_id"):
        session["full_name"] = user.full_name
        session["role"] = user.role
        session["username"] = user.username

    db_session_add(user)
    from auditlog import log_action
    log_action("update", "user", user.id, username)
    return jsonify(user.to_dict())


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_api("users", "delete")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # Owner protection
    if user.username == "admin" and user.role == "admin":
        return jsonify({"message": "لا يمكن حذف حساب المالك", "error_key": "users.ownerProtected"}), 403
    if user.id == session.get("user_id"):
        return jsonify({"message": "لا يمكنك حذف حسابك الحالي", "error_key": "users.cannotDeleteSelf"}), 400
    if user.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        return jsonify({"message": "لا يمكنك حذف آخر مدير", "error_key": "users.cannotDeleteLastAdmin"}), 400
    from auditlog import log_action
    log_action("delete", "user", user.id, user.username)
    # لا نحذف سجل التدقيق — نُبقيه مع إخفاء هوية المستخدم (audit immutability)
    AuditLog.query.filter_by(user_id=user.id).update(
        {"user_id": None}, synchronize_session=False)
    db.session.commit()
    db_session_delete(user)
    return jsonify({"success": True})


def db_session_add(obj):
    from database import db
    db.session.add(obj)
    db.session.commit()


def db_session_delete(obj):
    from database import db
    db.session.delete(obj)
    db.session.commit()


# ============ الملف الشخصي ============

@users_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        return jsonify({"message": "غير مسجل الدخول"}), 401
    data = request.get_json() or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()

    if not full_name:
        return jsonify({"message": "الاسم الكامل مطلوب", "error_key": "users.fullNameRequired"}), 400
    conflict = User.query.filter(User.email == email, User.id != user.id).first()
    if email and conflict:
        return jsonify({"message": "البريد الإلكتروني مستخدم بالفعل", "error_key": "users.emailExists"}), 409

    user.full_name = full_name
    user.email = email or user.email
    session["full_name"] = user.full_name
    db_session_add(user)
    from auditlog import log_action
    log_action("update", "user", user.id, user.username)
    return jsonify(user.to_dict())


@users_bp.route("/profile/password", methods=["PUT"])
@login_required
def change_password():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        return jsonify({"message": "غير مسجل الدخول"}), 401
    data = request.get_json() or {}
    current = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not check_password_hash(user.password_hash, current):
        return jsonify({"message": "كلمة المرور الحالية غير صحيحة", "error_key": "profile.wrongPassword"}), 400
    if (len(new_password) < 8
            or not any(c.isalpha() for c in new_password)
            or not any(c.isdigit() for c in new_password)):
        return jsonify({
            "message": "كلمة المرور يجب ألا تقل عن 8 أحرف وتحتوي على حروف وأرقام",
            "error_key": "profile.passwordWeak",
        }), 400

    user.password_hash = generate_password_hash(new_password)
    user.must_change_password = False
    db_session_add(user)
    from auditlog import log_action
    log_action("update", "user", user.id, "password_changed")
    return jsonify({"success": True})


# ============ سجل النشاط ============

@users_bp.route("/audit-logs", methods=["GET"])
@require_api("audit", "view")
def list_audit_logs():
    q = AuditLog.query
    entity = request.args.get("entity") or ""
    action = request.args.get("action") or ""
    search = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 200)

    if entity:
        q = q.filter(AuditLog.entity == entity)
    if action:
        q = q.filter(AuditLog.action == action)
    if search:
        like = f"%{search}%"
        q = q.filter(AuditLog.description.ilike(like) | AuditLog.username.ilike(like))

    logs = q.order_by(AuditLog.id.desc()).limit(limit).all()
    return jsonify([l.to_dict() for l in logs])
