"""بوابة العميل — Portal للعميل لعرض عقوده وأقساطه وصيانته."""
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session, current_app
from database import db
from models import SalesContract, Installment, PaymentPlan, MaintenanceRequest, RealEstateUnit, Customer, RentalContract, RentalPayment, ServiceCharge, OwnerAssociation
from permissions import require_api
from auditlog import log_action

portal_bp = Blueprint("portal", __name__)
portal_api_bp = Blueprint("portal_api", __name__, url_prefix="/api/portal")


@portal_bp.route("/portal")
def portal_page():
    return render_template("portal.html")


# بحث برقم العقد (بدون تسجيل دخول — للعميل) مع تحديد معدل
_portal_lookups = {}


def _get_limiter():
    """الحصول على المثيل المحدد للمعدل من التطبيق الحالي."""
    return current_app.extensions.get('limiter')


@portal_api_bp.route("/lookup", methods=["GET"])
def lookup():
    """بحث العميل عن عقده برقم العقد ورقم الهاتف/الهوية (بدون تسجيل ERP)."""
    import time
    ip = request.remote_addr or "unknown"
    key = f"{ip}"
    now = time.time()
    # حد بسيط: 10 محاولات / دقيقة
    hist = _portal_lookups.get(key, [])
    hist = [t for t in hist if now - t < 60]
    if len(hist) >= 10:
        return jsonify({"message": "محاولات كثيرة — حاول بعد دقيقة", "error_key": "portal.rateLimited"}), 429
    hist.append(now)
    _portal_lookups[key] = hist
    # تنظيف الذاكرة: إزالة المدخلات المنتهية إذا كبر القاموس
    if len(_portal_lookups) > 1000:
        for k in list(_portal_lookups.keys()):
            _portal_lookups[k] = [t for t in _portal_lookups[k] if now - t < 60]
            if not _portal_lookups[k]:
                del _portal_lookups[k]
            if len(_portal_lookups) <= 500:
                break

    contract_number = (request.args.get("contract_number") or "").strip()
    phone = (request.args.get("phone") or "").strip()
    if not contract_number:
        return jsonify({"message": "رقم العقد مطلوب"}), 400

    contract = SalesContract.query.filter_by(contract_number=contract_number).first()
    if not contract:
        return jsonify({"message": "العقد غير موجود"}), 404
    # تجاهل العقود المحذوفة
    if getattr(contract, 'deleted_at', None):
        return jsonify({"message": "العقد غير موجود"}), 404

    # تحقق إلزامي برقم الهاتف — تطبيع (إزالة غير رقمي)
    import re as _re
    def _norm(p): return _re.sub(r'\D', '', p or '')
    if contract.customer and contract.customer.phone:
        if not phone:
            return jsonify({"message": "رقم الهاتف مطلوب للتحقق", "error_key": "portal.phoneRequired"}), 400
        cust_phone_norm = _norm(contract.customer.phone)
        phone_norm = _norm(phone)
        # اسمح بمطابقة آخر 9 أرقام (يتجاوز اختلاف رمز البلد)
        if cust_phone_norm and phone_norm and cust_phone_norm[-9:] != phone_norm[-9:]:
            log_action("lookup_failed", "portal", contract.id, f"phone_mismatch {contract_number} ip={ip}")
            return jsonify({"message": "رقم الهاتف لا يطابق العقد", "error_key": "portal.phoneMismatch"}), 403

    # جمع البيانات
    unit = contract.unit
    plan = contract.payment_plan
    installments = []
    if plan:
        installments = [i.to_dict() if hasattr(i, 'to_dict') else {
            "id": i.id, "installment_number": i.installment_number,
            "amount": float(i.amount or 0), "paid_amount": float(i.paid_amount or 0),
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "status": i.status,
        } for i in plan.installments]

    maintenance = []
    if unit:
        maintenance = [m.to_dict() for m in MaintenanceRequest.query.filter_by(unit_id=unit.id).order_by(MaintenanceRequest.id.desc()).limit(10).all()]

    return jsonify({
        "contract": contract.to_dict(),
        "unit": unit.to_dict() if unit else None,
        "customer": {"full_name": contract.customer.full_name, "phone": contract.customer.phone} if contract.customer else None,
        "installments": installments,
        "maintenance": maintenance,
    })


@portal_api_bp.route("/my-contracts", methods=["GET"])
@require_api("realestate", "view")
def my_contracts():
    """للموظف: عرض عقود عميل محدد (بحث بالعميل)."""
    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        return jsonify({"message": "customer_id مطلوب"}), 400
    contracts = SalesContract.query.filter_by(customer_id=customer_id).order_by(SalesContract.id.desc()).all()
    return jsonify([c.to_dict() for c in contracts])


# ==================== Owner Portal ====================

@portal_api_bp.route("/owner/dashboard", methods=["GET"])
@require_api("realestate", "view")
def owner_dashboard():
    """لوحة تحكم المالك — ملخص الوحدات والعقود والتحصيلات."""
    owner_id = request.args.get("owner_id", type=int)
    if not owner_id:
        return jsonify({"message": "owner_id مطلوب"}), 400

    from models import RealEstateUnit, SalesContract, ServiceCharge, OwnerAssociation
    from sqlalchemy import func

    units = RealEstateUnit.query.filter_by(owner_id=owner_id).all()
    unit_ids = [u.id for u in units]

    # العقود
    contracts = SalesContract.query.filter(SalesContract.unit_id.in_(unit_ids)).all() if unit_ids else []

    # رسوم الخدمات
    charges = []
    if unit_ids:
        charges = ServiceCharge.query.filter(ServiceCharge.unit_id.in_(unit_ids)).all()

    # إحصائيات
    total_units = len(units)
    sold_units = len([u for u in units if u.status == 'sold'])
    available_units = len([u for u in units if u.status == 'available'])
    rented_units = len([u for u in units if u.status == 'rented'])

    total_contract_value = sum(float(c.net_amount or 0) for c in contracts)
    pending_charges = sum(float(c.amount or 0) - float(c.paid_amount or 0) for c in charges if c.status in ('pending', 'partial', 'overdue'))
    overdue_charges = len([c for c in charges if c.status == 'overdue'])

    # اتحاد الملاك
    associations = OwnerAssociation.query.join(RealEstateUnit, OwnerAssociation.project_id == RealEstateUnit.project_id).filter(RealEstateUnit.owner_id == owner_id).distinct().all()

    return jsonify({
        "owner_id": owner_id,
        "stats": {
            "total_units": total_units,
            "sold_units": sold_units,
            "available_units": available_units,
            "rented_units": rented_units,
            "total_contract_value": total_contract_value,
            "pending_charges": pending_charges,
            "overdue_charges": overdue_charges,
            "associations_count": len(associations),
        },
        "units": [u.to_dict() for u in units],
        "contracts": [c.to_dict() for c in contracts],
        "charges": [c.to_dict() for c in charges],
        "associations": [a.to_dict() for a in associations],
    })


@portal_api_bp.route("/owner/units", methods=["GET"])
@require_api("realestate", "view")
def owner_units():
    """قائمة وحدات المالك."""
    owner_id = request.args.get("owner_id", type=int)
    if not owner_id:
        return jsonify({"message": "owner_id مطلوب"}), 400
    units = RealEstateUnit.query.filter_by(owner_id=owner_id).all()
    return jsonify([u.to_dict() for u in units])


@portal_api_bp.route("/owner/contracts", methods=["GET"])
@require_api("realestate", "view")
def owner_contracts():
    """عقود وحدات المالك."""
    owner_id = request.args.get("owner_id", type=int)
    if not owner_id:
        return jsonify({"message": "owner_id مطلوب"}), 400
    units = RealEstateUnit.query.filter_by(owner_id=owner_id).all()
    unit_ids = [u.id for u in units]
    contracts = SalesContract.query.filter(SalesContract.unit_id.in_(unit_ids)).order_by(SalesContract.id.desc()).all() if unit_ids else []
    return jsonify([c.to_dict() for c in contracts])


@portal_api_bp.route("/owner/charges", methods=["GET"])
@require_api("realestate", "view")
def owner_charges():
    """رسوم خدمات وحدات المالك."""
    owner_id = request.args.get("owner_id", type=int)
    if not owner_id:
        return jsonify({"message": "owner_id مطلوب"}), 400
    units = RealEstateUnit.query.filter_by(owner_id=owner_id).all()
    unit_ids = [u.id for u in units]
    charges = ServiceCharge.query.filter(ServiceCharge.unit_id.in_(unit_ids)).order_by(ServiceCharge.due_date.desc()).all() if unit_ids else []
    return jsonify([c.to_dict() for c in charges])


# ==================== Tenant Portal ====================

@portal_api_bp.route("/tenant/dashboard", methods=["GET"])
@require_api("realestate", "view")
def tenant_dashboard():
    """لوحة تحكم المستأجر — ملخص العقود الإيجارية والمدفوعات."""
    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        return jsonify({"message": "customer_id مطلوب"}), 400

    from models import RentalContract, RentalPayment, MaintenanceRequest, RealEstateUnit

    contracts = RentalContract.query.filter_by(customer_id=customer_id).all()
    contract_ids = [c.id for c in contracts]

    payments = []
    overdue_payments = []
    if contract_ids:
        payments = RentalPayment.query.filter(RentalPayment.contract_id.in_(contract_ids)).order_by(RentalPayment.payment_date.desc()).all()
        overdue_payments = [p for p in payments if p.status == 'overdue']

    # طلبات الصيانة
    unit_ids = [c.unit_id for c in contracts if c.unit_id]
    maintenance = MaintenanceRequest.query.filter(MaintenanceRequest.unit_id.in_(unit_ids)).order_by(MaintenanceRequest.id.desc()).limit(10).all() if unit_ids else []

    total_monthly_rent = sum(float(c.monthly_rent or 0) for c in contracts)
    total_paid = sum(float(p.amount or 0) for p in payments if p.status == 'paid')

    return jsonify({
        "customer_id": customer_id,
        "stats": {
            "active_contracts": len([c for c in contracts if c.status == 'active']),
            "total_contracts": len(contracts),
            "total_monthly_rent": total_monthly_rent,
            "total_paid": total_paid,
            "pending_payments": len([p for p in payments if p.status in ('pending', 'partial')]),
            "overdue_payments": len(overdue_payments),
            "maintenance_requests": len(maintenance),
        },
        "contracts": [c.to_dict() for c in contracts],
        "payments": [p.to_dict() for p in payments],
        "maintenance": [m.to_dict() for m in maintenance],
    })


@portal_api_bp.route("/tenant/contracts", methods=["GET"])
@require_api("realestate", "view")
def tenant_contracts():
    """عقود المستأجر الإيجارية."""
    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        return jsonify({"message": "customer_id مطلوب"}), 400
    contracts = RentalContract.query.filter_by(customer_id=customer_id).order_by(RentalContract.id.desc()).all()
    return jsonify([c.to_dict() for c in contracts])


@portal_api_bp.route("/tenant/payments", methods=["GET"])
@require_api("realestate", "view")
def tenant_payments():
    """مدفوعات المستأجر."""
    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        return jsonify({"message": "customer_id مطلوب"}), 400
    contracts = RentalContract.query.filter_by(customer_id=customer_id).all()
    contract_ids = [c.id for c in contracts]
    payments = RentalPayment.query.filter(RentalPayment.contract_id.in_(contract_ids)).order_by(RentalPayment.payment_date.desc()).all() if contract_ids else []
    return jsonify([p.to_dict() for p in payments])


@portal_api_bp.route("/tenant/maintenance", methods=["GET"])
@require_api("realestate", "view")
def tenant_maintenance():
    """طلبات صيانة المستأجر."""
    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        return jsonify({"message": "customer_id مطلوب"}), 400
    contracts = RentalContract.query.filter_by(customer_id=customer_id).all()
    unit_ids = [c.unit_id for c in contracts if c.unit_id]
    maintenance = MaintenanceRequest.query.filter(MaintenanceRequest.unit_id.in_(unit_ids)).order_by(MaintenanceRequest.id.desc()).all() if unit_ids else []
    return jsonify([m.to_dict() for m in maintenance])


@portal_api_bp.route("/tenant/maintenance", methods=["POST"])
@require_api("realestate", "create")
def tenant_create_maintenance():
    """إنشاء طلب صيانة من المستأجر."""
    data = request.get_json() or {}
    required = ("unit_id", "issue_type")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400

    from models import MaintenanceRequest, RealEstateUnit
    unit = db.session.get(RealEstateUnit, data["unit_id"])
    if not unit:
        return jsonify({"message": "الوحدة غير موجودة"}), 404

    mr = MaintenanceRequest(
        unit_id=data["unit_id"],
        issue_type=data["issue_type"],
        description=data.get("description"),
        request_date=data.get("request_date") or datetime.now().date(),
        status="pending",
        assigned_to=data.get("assigned_to"),
        cost=data.get("cost"),
    )
    db.session.add(mr)
    db.session.commit()
    return jsonify(mr.to_dict()), 201
