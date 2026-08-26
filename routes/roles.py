"""Role & permission management endpoints (admin area)."""
from flask import Blueprint, request, jsonify, session
from database import db
from models import Role, User
from permissions import (
    MODULES,
    ACTIONS,
    get_role_permissions,
    require_api,
)

roles_bp = Blueprint("roles", __name__, url_prefix="/api/roles")


@roles_bp.route("/meta")
@require_api("roles", "view")
def meta():
    """Module/action metadata used by the roles page."""
    return jsonify({
        "modules": MODULES,
        "actions": ACTIONS,
    })


@roles_bp.route("", methods=["GET"])
@require_api("roles", "view")
def list_roles():
    roles = Role.query.order_by(Role.id.asc()).all()
    return jsonify([r.to_dict() for r in roles])


@roles_bp.route("", methods=["POST"])
@require_api("roles", "create")
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"message": "اسم الدور مطلوب", "error_key": "roles.nameRequired"}), 400
    if Role.query.filter_by(name=name).first():
        return jsonify({"message": "هذا الدور موجود بالفعل", "error_key": "roles.nameExists"}), 409

    role = Role(
        name=name,
        description=description,
        is_system=False,
        permissions=data.get("permissions") or {},
    )
    db.session.add(role)
    db.session.commit()
    return jsonify(role.to_dict()), 201


@roles_bp.route("/<int:role_id>", methods=["PUT"])
@require_api("roles", "edit")
def update_role(role_id):
    role = Role.query.get_or_404(role_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"message": "اسم الدور مطلوب", "error_key": "roles.nameRequired"}), 400
        conflict = Role.query.filter(Role.name == name, Role.id != role.id).first()
        if conflict:
            return jsonify({"message": "هذا الدور موجود بالفعل", "error_key": "roles.nameExists"}), 409
        role.name = name
    if "description" in data:
        role.description = (data["description"] or "").strip()
    if "permissions" in data:
        raw = data["permissions"] or {}
        clean = {}
        for m in MODULES:
            clean[m] = {a: bool(raw.get(m, {}).get(a, False)) for a in ACTIONS}
        role.permissions = clean

    db.session.commit()
    return jsonify(role.to_dict())


@roles_bp.route("/<int:role_id>", methods=["DELETE"])
@require_api("roles", "delete")
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    if role.is_system:
        return jsonify({"message": "لا يمكن حذف أدوار النظام", "error_key": "roles.cannotDeleteSystem"}), 400
    if role.name == "admin":
        return jsonify({"message": "لا يمكن حذف دور المدير", "error_key": "roles.cannotDeleteAdmin"}), 400
    users_count = User.query.filter_by(role=role.name).count()
    if users_count:
        return jsonify({
            "message": "لا يمكن حذف دور مستخدم بواسطة مستخدمين",
            "error_key": "roles.inUse",
        }), 400

    db.session.delete(role)
    db.session.commit()
    return jsonify({"success": True})
