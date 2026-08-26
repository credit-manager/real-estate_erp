"""البيع على الخارطة + خطة الدفع المجدولة DSP + سندات الملكية."""
from datetime import datetime
from flask import Blueprint, request, jsonify
from database import db
from models import ConstructionMilestone, DSPPlan, TitleDeed, Project, RealEstateUnit
from permissions import require_api
from auditlog import log_action

offplan_bp = Blueprint("offplan", __name__, url_prefix="/api/offplan")


# ============ Milestones ============

@offplan_bp.route("/milestones", methods=["GET"])
@require_api("projects", "view")
def list_milestones():
    q = ConstructionMilestone.query
    pid = request.args.get("project_id", type=int)
    if pid:
        q = q.filter_by(project_id=pid)
    return jsonify([m.to_dict() for m in q.order_by(ConstructionMilestone.id).all()])


@offplan_bp.route("/milestones", methods=["POST"])
@require_api("projects", "create")
def create_milestone():
    data = request.get_json() or {}
    if not data.get("project_id"):
        return jsonify({"message": "المشروع مطلوب", "error_key": "offplan.projectRequired"}), 400
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم المرحلة مطلوب", "error_key": "offplan.nameRequired"}), 400
    if not db.session.get(Project, data["project_id"]):
        return jsonify({"message": "المشروع غير موجود"}), 404
    from utils.pagination import parse_date
    m = ConstructionMilestone(
        project_id=data["project_id"],
        name=data["name"].strip(),
        description=(data.get("description") or "").strip(),
        target_date=parse_date(data.get("target_date")),
        completion_pct=data.get("completion_pct", 0),
        status=data.get("status", "pending"),
        weight=data.get("weight", 0),
    )
    db.session.add(m)
    db.session.commit()
    log_action("create", "milestone", m.id, m.name)
    return jsonify(m.to_dict()), 201


@offplan_bp.route("/milestones/<int:mid>", methods=["PUT"])
@require_api("projects", "edit")
def update_milestone(mid):
    m = db.session.get(ConstructionMilestone, mid)
    if not m:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    from utils.pagination import parse_date
    if "name" in data:
        m.name = (data["name"] or "").strip() or m.name
    if "description" in data:
        m.description = (data["description"] or "").strip()
    if "target_date" in data:
        m.target_date = parse_date(data["target_date"])
    if "completion_pct" in data:
        m.completion_pct = max(0, min(100, float(data["completion_pct"] or 0)))
        # تحديث الحالة تلقائياً
        if m.completion_pct >= 100:
            m.status = "completed"
        elif m.completion_pct > 0 and m.status == "pending":
            m.status = "in_progress"
    if "status" in data and data["status"] in ("pending", "in_progress", "completed", "delayed"):
        m.status = data["status"]
    if "weight" in data:
        m.weight = data["weight"]
    db.session.commit()
    log_action("update", "milestone", m.id, m.name)
    return jsonify(m.to_dict())


@offplan_bp.route("/milestones/<int:mid>", methods=["DELETE"])
@require_api("projects", "delete")
def delete_milestone(mid):
    m = db.session.get(ConstructionMilestone, mid)
    if not m:
        return jsonify({"message": "غير موجود"}), 404
    if DSPPlan.query.filter_by(milestone_id=mid).first():
        return jsonify({"message": "لا يمكن حذف مرحلة مرتبطة بخطة دفع", "error_key": "offplan.milestoneInUse"}), 400
    db.session.delete(m)
    db.session.commit()
    log_action("delete", "milestone", mid, m.name)
    return jsonify({"success": True})


# ============ DSP Plans ============

@offplan_bp.route("/dsp", methods=["GET"])
@require_api("projects", "view")
def list_dsp():
    q = DSPPlan.query
    pid = request.args.get("project_id", type=int)
    if pid:
        q = q.filter_by(project_id=pid)
    return jsonify([d.to_dict() for d in q.order_by(DSPPlan.id).all()])


@offplan_bp.route("/dsp", methods=["POST"])
@require_api("projects", "create")
def create_dsp():
    data = request.get_json() or {}
    if not data.get("project_id") or not (data.get("name") or "").strip():
        return jsonify({"message": "المشروع واسم البند مطلوبان"}), 400
    # تحقق من مجموع النسب
    existing_pct = sum(float(d.due_pct or 0) for d in DSPPlan.query.filter_by(project_id=data["project_id"]).all())
    new_pct = float(data.get("due_pct") or 0)
    if existing_pct + new_pct > 100.01:
        return jsonify({"message": f"مجموع النسب يتجاوز 100% (الحالي {existing_pct}%)", "error_key": "offplan.pctExceeds"}), 400
    d = DSPPlan(
        project_id=data["project_id"],
        milestone_id=data.get("milestone_id"),
        name=data["name"].strip(),
        due_pct=new_pct,
        amount_formula=data.get("amount_formula", "pct"),
        fixed_amount=data.get("fixed_amount", 0),
        due_days_after_milestone=data.get("due_days_after_milestone", 0),
        is_active=data.get("is_active", True),
    )
    db.session.add(d)
    db.session.commit()
    log_action("create", "dsp_plan", d.id, d.name)
    return jsonify(d.to_dict()), 201


@offplan_bp.route("/dsp/<int:did>", methods=["PUT"])
@require_api("projects", "edit")
def update_dsp(did):
    d = db.session.get(DSPPlan, did)
    if not d:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    # تحقق من مجموع النسب بعد التحديث
    if "due_pct" in data:
        try:
            new_pct = float(data["due_pct"])
            if new_pct < 0 or new_pct > 100:
                return jsonify({"message": "النسبة يجب أن تكون بين 0 و 100"}), 400
            other_pct = sum(float(x.due_pct or 0) for x in DSPPlan.query.filter(DSPPlan.project_id == d.project_id, DSPPlan.id != did).all())
            if other_pct + new_pct > 100.01:
                return jsonify({"message": f"مجموع النسب يتجاوز 100% (الحالي {other_pct}%)", "error_key": "offplan.pctExceeds"}), 400
            d.due_pct = new_pct
        except (ValueError, TypeError):
            return jsonify({"message": "نسبة غير صالحة"}), 400
    for field in ("name", "amount_formula", "is_active"):
        if field in data:
            setattr(d, field, data[field])
    if "fixed_amount" in data:
        try:
            fa = float(data["fixed_amount"])
            if fa < 0:
                return jsonify({"message": "المبلغ الثابت لا يمكن أن يكون سالباً"}), 400
            d.fixed_amount = fa
        except (ValueError, TypeError):
            return jsonify({"message": "مبلغ غير صالح"}), 400
    if "milestone_id" in data:
        mid = data["milestone_id"]
        if mid and not db.session.get(ConstructionMilestone, mid):
            return jsonify({"message": "المرحلة غير موجودة"}), 404
        d.milestone_id = mid
    db.session.commit()
    log_action("update", "dsp_plan", d.id, d.name)
    return jsonify(d.to_dict())


@offplan_bp.route("/dsp/<int:did>", methods=["DELETE"])
@require_api("projects", "delete")
def delete_dsp(did):
    d = db.session.get(DSPPlan, did)
    if not d:
        return jsonify({"message": "غير موجود"}), 404
    db.session.delete(d)
    db.session.commit()
    return jsonify({"success": True})


@offplan_bp.route("/dsp/check/<int:contract_id>", methods=["GET"])
@require_api("realestate", "view")
def dsp_due_for_contract(contract_id):
    """فحص الدفعات المستحقة لعقد معين بناءً على المراحل المكتملة."""
    from models import SalesContract
    contract = db.session.get(SalesContract, contract_id)
    if not contract:
        return jsonify({"message": "العقد غير موجود"}), 404
    # جد خطة DSP للمشروع المرتبط بالوحدة
    unit = contract.unit
    if not unit or not unit.project_id:
        return jsonify({"due": [], "not_due": []})
    plans = DSPPlan.query.filter_by(project_id=unit.project_id, is_active=True).all()
    due, not_due = [], []
    for p in plans:
        (due if p.is_due() else not_due).append(p.to_dict())
    return jsonify({"due": due, "not_due": not_due, "total_due_pct": sum(float(x["due_pct"]) for x in due)})


# ============ Title Deeds ============

@offplan_bp.route("/deeds", methods=["GET"])
@require_api("realestate", "view")
def list_deeds():
    q = TitleDeed.query
    uid = request.args.get("unit_id", type=int)
    if uid:
        q = q.filter_by(unit_id=uid)
    return jsonify([d.to_dict() for d in q.order_by(TitleDeed.id.desc()).all()])


@offplan_bp.route("/deeds", methods=["POST"])
@require_api("realestate", "create")
def create_deed():
    data = request.get_json() or {}
    if not data.get("unit_id") or not (data.get("deed_number") or "").strip():
        return jsonify({"message": "الوحدة ورقم الصك مطلوبان"}), 400
    if not db.session.get(RealEstateUnit, data["unit_id"]):
        return jsonify({"message": "الوحدة غير موجودة"}), 404
    from utils.pagination import parse_date
    from sqlalchemy.exc import IntegrityError
    d = TitleDeed(
        unit_id=data["unit_id"],
        deed_number=data["deed_number"].strip(),
        owner_name=(data.get("owner_name") or "").strip(),
        owner_id_number=(data.get("owner_id_number") or "").strip(),
        issue_date=parse_date(data.get("issue_date")),
        area=data.get("area"),
        deed_type=data.get("deed_type", "freehold"),
        status=data.get("status", "active"),
        previous_deed_id=data.get("previous_deed_id"),
        notes=(data.get("notes") or "").strip(),
    )
    db.session.add(d)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "رقم الصك مكرر"}), 409
    log_action("create", "title_deed", d.id, d.deed_number)
    return jsonify(d.to_dict()), 201


@offplan_bp.route("/deeds/<int:did>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_deed(did):
    d = db.session.get(TitleDeed, did)
    if not d:
        return jsonify({"message": "غير موجود"}), 404
    if TitleDeed.query.filter_by(previous_deed_id=did).first():
        return jsonify({"message": "لا يمكن حذف صك له صكوك لاحقة"}), 400
    db.session.delete(d)
    db.session.commit()
    return jsonify({"success": True})
