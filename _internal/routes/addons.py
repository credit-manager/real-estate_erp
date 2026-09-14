"""إضافات عقارية: DMS + اتحاد ملاك + تقييم آلي AVM + حاسبة تمويل."""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename

from database import db
from models import UnitDocument, OwnerAssociation, ServiceCharge, RealEstateUnit, Project
from permissions import require_api
from auditlog import log_action

addons_bp = Blueprint("addons", __name__, url_prefix="/api/addons")

ALLOWED_DOC_TYPES = {"title_deed", "contract", "id_copy", "plan", "photo", "other"}
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/webp", "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


# ============ DMS — مستندات الوحدة ============

@addons_bp.route("/units/<int:unit_id>/documents", methods=["GET"])
@require_api("realestate", "view")
def list_docs(unit_id):
    docs = UnitDocument.query.filter_by(unit_id=unit_id).filter(UnitDocument.deleted_at.is_(None)).order_by(UnitDocument.id.desc()).all()
    return jsonify([d.to_dict() for d in docs])


@addons_bp.route("/units/<int:unit_id>/documents", methods=["POST"])
@require_api("realestate", "create")
def create_doc(unit_id):
    if not db.session.get(RealEstateUnit, unit_id):
        return jsonify({"message": "الوحدة غير موجودة"}), 404
    data = request.get_json() or {}
    doc_type = (data.get("doc_type") or "other").strip()
    if doc_type not in ALLOWED_DOC_TYPES:
        doc_type = "other"
    if not (data.get("title") or "").strip():
        return jsonify({"message": "عنوان المستند مطلوب"}), 400
    # نسخ إصدار — استخدم max(version) بدل first()
    try:
        file_size = int(data.get("file_size") or 0) if data.get("file_size") is not None else None
        if file_size is not None and (file_size < 0 or file_size > 50 * 1024 * 1024):
            return jsonify({"message": "حجم الملف غير صالح"}), 400
    except (TypeError, ValueError):
        return jsonify({"message": "حجم الملف غير صالح"}), 400
    mime = (data.get("mime_type") or "").strip()
    if mime and mime not in ALLOWED_MIME:
        return jsonify({"message": "نوع الملف غير مدعوم"}), 400
    file_path = (data.get("file_path") or "").strip()
    if file_path and (".." in file_path or file_path.startswith("/") or file_path.startswith("\\")):
        return jsonify({"message": "مسار الملف غير صالح"}), 400
    max_ver = db.session.query(db.func.max(UnitDocument.version)).filter_by(unit_id=unit_id, title=data["title"].strip(), doc_type=doc_type).scalar()
    version = (int(max_ver) + 1) if max_ver else 1
    doc = UnitDocument(
        unit_id=unit_id,
        doc_type=doc_type,
        title=data["title"].strip(),
        file_path=file_path,
        file_size=file_size,
        mime_type=mime,
        version=version,
        notes=(data.get("notes") or "").strip(),
        uploaded_by=session.get("user_id"),
    )
    db.session.add(doc)
    db.session.commit()
    log_action("create", "unit_document", doc.id, doc.title)
    return jsonify(doc.to_dict()), 201


@addons_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_doc(doc_id):
    doc = db.session.get(UnitDocument, doc_id)
    if not doc:
        return jsonify({"message": "غير موجود"}), 404
    doc.deleted_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True})


# ============ HOA — اتحاد الملاك ============

@addons_bp.route("/hoa", methods=["GET"])
@require_api("realestate", "view")
def list_hoa():
    return jsonify([h.to_dict() for h in OwnerAssociation.query.all()])


@addons_bp.route("/hoa", methods=["POST"])
@require_api("realestate", "create")
def create_hoa():
    data = request.get_json() or {}
    if not data.get("project_id") or not (data.get("name") or "").strip():
        return jsonify({"message": "المشروع والاسم مطلوبان"}), 400
    if OwnerAssociation.query.filter_by(project_id=data["project_id"]).first():
        return jsonify({"message": "يوجد اتحاد ملاك لهذا المشروع مسبقاً"}), 409
    hoa = OwnerAssociation(
        project_id=data["project_id"],
        name=data["name"].strip(),
        annual_fee_per_sqm=data.get("annual_fee_per_sqm", 0),
        status=data.get("status", "active"),
        notes=(data.get("notes") or "").strip(),
    )
    db.session.add(hoa)
    db.session.commit()
    log_action("create", "owner_association", hoa.id, hoa.name)
    return jsonify(hoa.to_dict()), 201


@addons_bp.route("/hoa/<int:hoa_id>/charges", methods=["GET"])
@require_api("realestate", "view")
def list_charges(hoa_id):
    hoa = db.session.get(OwnerAssociation, hoa_id)
    if not hoa:
        return jsonify({"message": "غير موجود"}), 404
    q = ServiceCharge.query.filter_by(association_id=hoa_id)
    unit_id = request.args.get("unit_id", type=int)
    if unit_id:
        q = q.filter_by(unit_id=unit_id)
    return jsonify([c.to_dict() for c in q.order_by(ServiceCharge.due_date.desc()).all()])


@addons_bp.route("/hoa/<int:hoa_id>/charges", methods=["POST"])
@require_api("realestate", "create")
def create_charge(hoa_id):
    hoa = db.session.get(OwnerAssociation, hoa_id)
    if not hoa:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    if not data.get("unit_id") or not data.get("period") or not data.get("amount"):
        return jsonify({"message": "الوحدة والفترة والمبلغ مطلوبة"}), 400
    if not db.session.get(RealEstateUnit, data["unit_id"]):
        return jsonify({"message": "الوحدة غير موجودة"}), 404
    try:
        amt = Decimal(str(data["amount"]))
        if amt <= 0 or amt > Decimal("1000000000"):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"message": "المبلغ غير صالح"}), 400
    if data.get("status") and data["status"] not in ("pending", "paid", "overdue", "waived", "partial"):
        return jsonify({"message": "حالة غير صالحة"}), 400
    from utils.pagination import parse_date
    ch = ServiceCharge(
        association_id=hoa_id,
        unit_id=data["unit_id"],
        period=data["period"].strip(),
        amount=amt,
        due_date=parse_date(data.get("due_date")),
        status=data.get("status", "pending"),
        notes=(data.get("notes") or "").strip(),
    )
    db.session.add(ch)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "فشل إنشاء الرسوم"}), 400
    log_action("create", "service_charge", ch.id, ch.period)
    return jsonify(ch.to_dict()), 201


@addons_bp.route("/charges/<int:cid>/pay", methods=["POST"])
@require_api("realestate", "edit")
def pay_charge(cid):
    # قفل الصف لمنع race condition
    ch = db.session.query(ServiceCharge).filter_by(id=cid).with_for_update().first()
    if not ch:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    try:
        amount = Decimal(str(data.get("amount") or 0))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"message": "المبلغ غير صالح"}), 400
    if amount <= 0 or amount > Decimal("1000000000"):
        return jsonify({"message": "المبلغ غير صالح"}), 400
    balance = Decimal(str(ch.amount or 0)) - Decimal(str(ch.paid_amount or 0))
    if amount > balance:
        return jsonify({"message": "المبلغ يتجاوز الرصيد"}), 400
    ch.paid_amount = Decimal(str(ch.paid_amount or 0)) + amount
    if ch.paid_amount >= ch.amount:
        ch.status = "paid"
    elif ch.paid_amount > 0:
        ch.status = "partial"
    # تحديث رصيد الاتحاد مع قفل
    hoa = db.session.query(OwnerAssociation).filter_by(id=ch.association_id).with_for_update().first()
    if hoa:
        hoa.collected_amount = Decimal(str(hoa.collected_amount or 0)) + amount
        hoa.balance = Decimal(str(hoa.balance or 0)) + amount
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "فشل السداد"}), 400
    log_action("pay", "service_charge", ch.id, f"{amount}")
    return jsonify(ch.to_dict())


# ============ AVM — تقييم آلي مبسّط ============

@addons_bp.route("/valuation", methods=["GET"])
@require_api("realestate", "view")
def avm_valuation():
    """تقييم آلي: متوسط سعر المتر في المشروع × مساحة الوحدة + هامش السوق."""
    unit_id = request.args.get("unit_id", type=int)
    if not unit_id:
        return jsonify({"message": "unit_id مطلوب"}), 400
    unit = db.session.get(RealEstateUnit, unit_id)
    if not unit:
        return jsonify({"message": "الوحدة غير موجودة"}), 404

    # متوسط سعر المتر في نفس المشروع (وحدات مباعة فقط)
    from sqlalchemy import func
    avg_q = db.session.query(func.avg(RealEstateUnit.price / func.nullif(RealEstateUnit.area, 0))).filter(
        RealEstateUnit.project_id == unit.project_id,
        RealEstateUnit.status == "sold",
        RealEstateUnit.area > 0,
        RealEstateUnit.price > 0,
        RealEstateUnit.deleted_at.is_(None),
    ).scalar()

    if avg_q and float(avg_q) > 0:
        avg_price_per_sqm = float(avg_q)
        source = "project_sold_avg"
    else:
        # بديل: متوسط كل وحدات المشروع
        avg_q2 = db.session.query(func.avg(RealEstateUnit.price / func.nullif(RealEstateUnit.area, 0))).filter(
            RealEstateUnit.project_id == unit.project_id,
            RealEstateUnit.area > 0,
            RealEstateUnit.price > 0,
            RealEstateUnit.deleted_at.is_(None),
        ).scalar()
        avg_price_per_sqm = float(avg_q2 or 0)
        source = "project_avg" if avg_price_per_sqm else "no_data"

    area = float(unit.area or 0)
    estimated = round(avg_price_per_sqm * area, 2) if avg_price_per_sqm and area else 0
    current = float(unit.price or 0)
    diff_pct = round((estimated - current) / current * 100, 1) if current else 0

    return jsonify({
        "unit_id": unit.id,
        "unit_code": unit.unit_code,
        "area": area,
        "current_price": current,
        "avg_price_per_sqm": round(avg_price_per_sqm, 2),
        "estimated_value": estimated,
        "diff_pct": diff_pct,
        "source": source,
        "confidence": "high" if source == "project_sold_avg" else "medium" if source == "project_avg" else "low",
    })


# ============ حاسبة التمويل ============

@addons_bp.route("/mortgage-calc", methods=["GET"])
@require_api("realestate", "view")
def mortgage_calc():
    """حاسبة القسط الشهري: PMT = P*r*(1+r)^n / ((1+r)^n -1)"""
    try:
        price = float(request.args.get("price", 0))
        down = float(request.args.get("down", 0))
        rate = float(request.args.get("rate", 0))  # سنوي %
        years = int(request.args.get("years", 20))
    except (TypeError, ValueError):
        return jsonify({"message": "معاملات غير صالحة"}), 400

    if price <= 0 or years <= 0:
        return jsonify({"message": "السعر والمدة مطلوبان"}), 400

    principal = max(0, price - down)
    n = years * 12
    if rate <= 0:
        monthly = principal / n if n else 0
        total = principal
        total_interest = 0
    else:
        r = rate / 100 / 12
        monthly = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
        total = monthly * n
        total_interest = total - principal

    return jsonify({
        "price": price,
        "down_payment": down,
        "principal": round(principal, 2),
        "annual_rate": rate,
        "years": years,
        "months": n,
        "monthly_payment": round(monthly, 2),
        "total_paid": round(total, 2),
        "total_interest": round(total_interest, 2),
    })
