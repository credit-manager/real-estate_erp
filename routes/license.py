"""License management & owner protection routes."""
from flask import Blueprint, request, jsonify, session, render_template
from datetime import datetime, timezone, timedelta
from database import db
from models import User, License, LicenseActivity, OwnerNotification, AuditLog
from permissions import require_api, require_page, admin_required
from auditlog import log_action
import json

license_bp = Blueprint("license", __name__, url_prefix="/license")

OWNER_USERNAME = "admin"
OWNER_ROLE = "admin"


# ── License Validation (called from before_request) ───────────
def validate_license():
    """Return (is_valid, error_message). Called from app.py before_request."""
    try:
        active = License.query.filter_by(is_active=True).first()
        if not active:
            return True, None  # No license required in dev
        if active.expires_at < datetime.now(timezone.utc):
            return False, " expired"
        return True, None
    except Exception:
        return True, None  # Graceful if table doesn't exist yet


def get_active_license():
    """Return the current active license or None."""
    try:
        return License.query.filter_by(is_active=True).first()
    except Exception:
        return None


# ── Owner Protection ──────────────────────────────────────────
def is_owner(user_id=None):
    uid = user_id or session.get("user_id")
    if not uid:
        return False
    user = db.session.get(User, uid)
    return user and user.username == OWNER_USERNAME and user.role == OWNER_ROLE


def protect_owner_from_modify(target_user_id):
    """Raise if someone tries to modify/delete the owner."""
    target = db.session.get(User, target_user_id)
    if target and target.username == OWNER_USERNAME:
        return True
    return False


# ── Activity Logging ──────────────────────────────────────────
def log_license_activity(action, details="", user_id=None, username=None):
    try:
        lic = get_active_license()
        db.session.add(LicenseActivity(
            license_id=lic.id if lic else None,
            user_id=user_id or session.get("user_id"),
            username=username or session.get("username"),
            action=action,
            details=details[:300] if details else "",
            ip_address=request.remote_addr or "",
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def create_owner_notification(title, message, notif_type="user_action", related_user=None):
    try:
        db.session.add(OwnerNotification(
            title=title[:200],
            message=message[:1000],
            notification_type=notif_type,
            related_user=related_user,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── License Management Pages ──────────────────────────────────
@license_bp.route("/")
@require_page("settings", "view")
def license_page():
    return render_template("license_management.html")


# ── License API ───────────────────────────────────────────────
@license_bp.route("/api/licenses", methods=["GET"])
@require_page("settings", "view")
def list_licenses():
    try:
        licenses = License.query.order_by(License.created_at.desc()).all()
        return jsonify({"success": True, "data": [l.to_dict() for l in licenses]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@license_bp.route("/api/licenses", methods=["POST"])
@require_page("settings", "edit")
@admin_required
def create_license():
    data = request.get_json(silent=True) or {}
    required = ["company_name", "contact_name", "contact_email", "license_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"success": False, "message": f"Missing: {field}"}), 400

    lic_type = data["license_type"]
    if lic_type not in ("trial", "annual", "biennial"):
        return jsonify({"success": False, "message": "Invalid type"}), 400

    try:
        max_users = int(data.get("max_users", 10))
        max_users = max(1, min(max_users, 10000))
    except (TypeError, ValueError):
        max_users = 10

    duration = License.get_duration(lic_type)
    license_key = License.generate_key()

    lic = License(
        license_key=license_key,
        company_name=data["company_name"],
        contact_name=data["contact_name"],
        contact_email=data["contact_email"],
        contact_phone=data.get("contact_phone", ""),
        license_type=lic_type,
        max_users=max_users,
        expires_at=datetime.now(timezone.utc) + duration,
        is_active=True,
        notes=data.get("notes", ""),
        created_by=session.get("user_id"),
    )
    db.session.add(lic)
    db.session.commit()

    log_action("create", "license", lic.id, f"key={license_key} type={lic_type} company={data['company_name']}")
    return jsonify({"success": True, "data": lic.to_dict()}), 201


@license_bp.route("/api/licenses/<int:lid>/deactivate", methods=["POST"])
@require_page("settings", "edit")
@admin_required
def deactivate_license(lid):
    lic = db.session.get(License, lid)
    if not lic:
        return jsonify({"success": False, "message": "Not found"}), 404
    lic.is_active = False
    db.session.commit()
    log_action("deactivate", "license", lic.id, f"key={lic.license_key}")
    return jsonify({"success": True})


@license_bp.route("/api/licenses/<int:lid>/activate", methods=["POST"])
@require_page("settings", "edit")
@admin_required
def activate_license(lid):
    lic = db.session.get(License, lid)
    if not lic:
        return jsonify({"success": False, "message": "Not found"}), 404
    if lic.expires_at < datetime.now(timezone.utc):
        return jsonify({"success": False, "message": "License expired"}), 400
    lic.is_active = True
    db.session.commit()
    log_action("activate", "license", lic.id, f"key={lic.license_key}")
    return jsonify({"success": True})


@license_bp.route("/api/licenses/<int:lid>", methods=["DELETE"])
@require_page("settings", "edit")
@admin_required
def delete_license(lid):
    lic = db.session.get(License, lid)
    if not lic:
        return jsonify({"success": False, "message": "Not found"}), 404
    log_action("delete", "license", lic.id, f"key={lic.license_key} company={lic.company_name}")
    db.session.delete(lic)
    db.session.commit()
    return jsonify({"success": True})


# ── Activity API ──────────────────────────────────────────────
@license_bp.route("/api/activity", methods=["GET"])
@require_page("audit", "view")
def list_activity():
    try:
        q = LicenseActivity.query.order_by(LicenseActivity.created_at.desc())
        limit = min(int(request.args.get("limit", 100)), 500)
        activities = q.limit(limit).all()
        return jsonify({"success": True, "data": [a.to_dict() for a in activities]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@license_bp.route("/api/activity/login", methods=["POST"])
def log_user_login():
    """Called from auth.py after successful login."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    user_id = data.get("user_id")

    log_license_activity("login", f"user={username}", user_id, username)

    if user_id:
        user = db.session.get(User, user_id)
        if user and user.username != OWNER_USERNAME:
            create_owner_notification(
                title=f"دخول مستخدم: {username}",
                message=f"المستخدم {user.full_name} ({username}) قام بتسجيل الدخول من {request.remote_addr}",
                notif_type="login",
                related_user=username,
            )
    return jsonify({"success": True})


# ── Notifications API ─────────────────────────────────────────
@license_bp.route("/api/notifications", methods=["GET"])
@require_page("settings", "view")
def list_notifications():
    try:
        q = OwnerNotification.query.order_by(OwnerNotification.created_at.desc())
        limit = min(int(request.args.get("limit", 50)), 200)
        notifs = q.limit(limit).all()
        unread = OwnerNotification.query.filter_by(is_read=False).count()
        return jsonify({"success": True, "data": [n.to_dict() for n in notifs], "unread": unread})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@license_bp.route("/api/notifications/read", methods=["POST"])
@require_page("settings", "view")
def mark_notifications_read():
    try:
        OwnerNotification.query.filter_by(is_read=False).update({"is_read": True})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False}), 500


@license_bp.route("/api/license-status", methods=["GET"])
def license_status():
    """Public endpoint for checking license status."""
    lic = get_active_license()
    if not lic:
        return jsonify({"licensed": False, "message": "No license"})
    return jsonify({
        "licensed": True,
        "valid": lic.is_valid(),
        "days_remaining": lic.days_remaining(),
        "expires_at": lic.expires_at.isoformat(),
        "license_type": lic.license_type,
        "company_name": lic.company_name,
    })
