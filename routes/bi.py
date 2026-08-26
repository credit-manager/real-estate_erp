"""BI Embedded — Superset/Metabase دمج اللوحات."""
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, current_app
from sqlalchemy.exc import IntegrityError

from database import db
from models import BIProvider, BIDashboard, BIFilterTemplate
from permissions import require_api
from auditlog import log_action

bi_bp = Blueprint("bi", __name__, url_prefix="/api/bi")


# ==================== Providers ====================

@bi_bp.route("/providers", methods=["GET"])
@require_api("reports", "view")
def list_providers():
    providers = BIProvider.query.filter_by(is_active=True).all()
    return jsonify([p.to_dict() for p in providers])


@bi_bp.route("/providers", methods=["POST"])
@require_api("reports", "create")
def create_provider():
    data = request.get_json() or {}
    required = ("name", "display_name", "base_url")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if BIProvider.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "مزود بهذا الاسم موجود"}), 409

    provider = BIProvider(
        name=data["name"],
        display_name=data["display_name"],
        base_url=data["base_url"],
        api_key=data.get("api_key"),
        secret_key=data.get("secret_key"),
        is_active=data.get("is_active", True),
        is_default=data.get("is_default", False),
        config_json=data.get("config"),
    )
    db.session.add(provider)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "خطأ في الحفظ"}), 500
    log_action("create", "bi_provider", provider.id, provider.display_name)
    return jsonify(provider.to_dict()), 201


@bi_bp.route("/providers/<int:pid>", methods=["PUT"])
@require_api("reports", "edit")
def update_provider(pid):
    provider = db.session.get(BIProvider, pid)
    if not provider:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("display_name", "base_url", "api_key", "secret_key", "is_active", "is_default"):
        if field in data:
            setattr(provider, field, data[field])
    if "config" in data:
        provider.config_json = data["config"]
    db.session.commit()
    log_action("update", "bi_provider", provider.id, provider.display_name)
    return jsonify(provider.to_dict())


@bi_bp.route("/providers/<int:pid>", methods=["DELETE"])
@require_api("reports", "delete")
def delete_provider(pid):
    provider = db.session.get(BIProvider, pid)
    if not provider:
        return jsonify({"message": "غير موجود"}), 404
    if BIDashboard.query.filter_by(provider_id=pid).first():
        return jsonify({"message": "لا يمكن حذف مزود له لوحات"}), 400
    db.session.delete(provider)
    db.session.commit()
    log_action("delete", "bi_provider", pid, provider.display_name)
    return jsonify({"success": True})


# ==================== Dashboards ====================

@bi_bp.route("/dashboards", methods=["GET"])
@require_api("reports", "view")
def list_dashboards():
    q = BIDashboard.query.filter_by(is_active=True)
    cat = request.args.get("category")
    if cat:
        q = q.filter_by(category=cat)
    provider = request.args.get("provider_id", type=int)
    if provider:
        q = q.filter_by(provider_id=provider)
    return jsonify([d.to_dict() for d in q.order_by(BIDashboard.id.desc()).all()])


@bi_bp.route("/dashboards", methods=["POST"])
@require_api("reports", "create")
def create_dashboard():
    data = request.get_json() or {}
    required = ("provider_id", "external_id", "title")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if not db.session.get(BIProvider, data["provider_id"]):
        return jsonify({"message": "المزود غير موجود"}), 404

    dash = BIDashboard(
        provider_id=data["provider_id"],
        external_id=data["external_id"],
        title=data["title"],
        description=data.get("description"),
        category=data.get("category"),
        is_public=data.get("is_public", False),
        allowed_roles=data.get("allowed_roles"),
        iframe_width=data.get("iframe_width", "100%"),
        iframe_height=data.get("iframe_height", "600px"),
        filter_params=data.get("filter_params"),
        is_active=data.get("is_active", True),
    )
    db.session.add(dash)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "خطأ في الحفظ"}), 500
    log_action("create", "bi_dashboard", dash.id, dash.title)
    return jsonify(dash.to_dict()), 201


@bi_bp.route("/dashboards/<int:did>", methods=["PUT"])
@require_api("reports", "edit")
def update_dashboard(did):
    dash = db.session.get(BIDashboard, did)
    if not dash:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("title", "description", "category", "is_public", "allowed_roles", "iframe_width", "iframe_height", "is_active"):
        if field in data:
            setattr(dash, field, data[field])
    if "filter_params" in data:
        dash.filter_params = data["filter_params"]
    if "provider_id" in data:
        if db.session.get(BIProvider, data["provider_id"]):
            dash.provider_id = data["provider_id"]
    db.session.commit()
    log_action("update", "bi_dashboard", dash.id, dash.title)
    return jsonify(dash.to_dict())


@bi_bp.route("/dashboards/<int:did>", methods=["DELETE"])
@require_api("reports", "delete")
def delete_dashboard(did):
    dash = db.session.get(BIDashboard, did)
    if not dash:
        return jsonify({"message": "غير موجود"}), 404
    db.session.delete(dash)
    db.session.commit()
    log_action("delete", "bi_dashboard", did, dash.title)
    return jsonify({"success": True})


@bi_bp.route("/dashboards/<int:did>/embed", methods=["GET"])
@require_api("reports", "view")
def get_embed_url(did):
    """الحصول على رابط التضمين (iframe) للوحة."""
    dash = db.session.get(BIDashboard, did)
    if not dash:
        return jsonify({"message": "غير موجود"}), 404
    url = dash.get_embed_url()
    if not url:
        return jsonify({"message": "المزود غير مكوّن"}), 400
    return jsonify({"embed_url": url, "width": dash.iframe_width, "height": dash.iframe_height})


@bi_bp.route("/dashboards/categories", methods=["GET"])
@require_api("reports", "view")
def list_categories():
    cats = db.session.query(BIDashboard.category).filter(BIDashboard.category.isnot(None)).distinct().all()
    return jsonify([{"category": c[0]} for c in cats if c[0]])


# ==================== Filter Templates ====================

@bi_bp.route("/filters", methods=["GET"])
@require_api("reports", "view")
def list_filters():
    provider = request.args.get("provider_id", type=int)
    q = BIFilterTemplate.query
    if provider:
        q = q.filter_by(provider_id=provider)
    return jsonify([f.to_dict() for f in q.order_by(BIFilterTemplate.sort_order).all()])


@bi_bp.route("/filters", methods=["POST"])
@require_api("reports", "create")
def create_filter():
    data = request.get_json() or {}
    required = ("provider_id", "name", "filter_key")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if not db.session.get(BIProvider, data["provider_id"]):
        return jsonify({"message": "المزود غير موجود"}), 404

    f = BIFilterTemplate(
        provider_id=data["provider_id"],
        name=data["name"],
        filter_key=data["filter_key"],
        filter_type=data.get("filter_type", "select"),
        label=data.get("label"),
        default_value=data.get("default_value"),
        options_json=data.get("options"),
        is_required=data.get("is_required", False),
        sort_order=data.get("sort_order", 0),
    )
    db.session.add(f)
    db.session.commit()
    return jsonify(f.to_dict()), 201


@bi_bp.route("/filters/<int:fid>", methods=["PUT"])
@require_api("reports", "edit")
def update_filter(fid):
    f = db.session.get(BIFilterTemplate, fid)
    if not f:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("name", "filter_key", "filter_type", "label", "default_value", "options", "is_required", "sort_order"):
        if field in data:
            if field == "options":
                f.options_json = data[field]
            else:
                setattr(f, field, data[field])
    db.session.commit()
    return jsonify(f.to_dict())


@bi_bp.route("/filters/<int:fid>", methods=["DELETE"])
@require_api("reports", "delete")
def delete_filter(fid):
    f = db.session.get(BIFilterTemplate, fid)
    if not f:
        return jsonify({"message": "غير موجود"}), 404
    db.session.delete(f)
    db.session.commit()
    return jsonify({"success": True})


# ==================== Embedded Dashboard Page ====================

@bi_bp.route("/embed/<int:did>")
def embed_dashboard(did):
    """صفحة تضمين اللوحة (للـ iframe)."""
    dash = db.session.get(BIDashboard, did)
    if not dash or not dash.is_active:
        return render_template("bi_embed.html", error="اللوحة غير متاحة"), 404
    return render_template("bi_embed.html", dashboard=dash)