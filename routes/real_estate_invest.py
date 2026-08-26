from flask import Blueprint, request, jsonify
from datetime import datetime
from database import db
from models import (
    RealEstateUnit, Employee, Customer,
    Building, Floor, UnitType, Owner, UnitPriceHistory,
    Reservation, Allocation, SalesContract, Commission,
    UnitDelivery, MaintenanceRequest, UnitShare, Broker,
    PaymentPlan, Installment,
    DeliveryChecklistItem, TenantScreening, UnitMortgage,
)
from permissions import require_api
from utils.pagination import paged_or_cap

re_bp = Blueprint("realestate_api", __name__, url_prefix="/api/realestate")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    from auditlog import log_action
    log_action(action, entity, entity_id, description)


def _next_contract_number():
    year = datetime.now().year
    prefix = f"SC-{year}-"
    last = (
        SalesContract.query
        .filter(SalesContract.contract_number.like(prefix + "%"))
        .order_by(SalesContract.id.desc())
        .first()
    )
    if last and last.contract_number:
        try:
            seq = int(last.contract_number.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _set_unit_status(unit_id, status):
    unit = db.session.get(RealEstateUnit, unit_id)
    if unit:
        unit.status = status


def _unit_has_live_hold(unit):
    """هل على الوحدة حجز/تخصيص نشط أو عقد بيع ساري؟"""
    if not unit:
        return True
    if any(r.status == "active" for r in unit.reservations):
        return True
    if any(a.status == "active" for a in unit.allocations):
        return True
    if any(c.status != "cancelled" for c in unit.sales_contracts):
        return True
    return False


def _unit_is_free(unit):
    """هل يمكن إرجاع الوحدة إلى (متاحة)؟"""
    return not _unit_has_live_hold(unit)


def _release_unit_if_reserved(unit_id):
    """يحرّر الوحدة من حالة (محجوزة) إن لم تبقَ أي أسباب احتكار."""
    unit = db.session.get(RealEstateUnit, unit_id)
    if unit and unit.status == "reserved" and _unit_is_free(unit):
        unit.status = "available"
        return True
    return False


def _expire_stale_reservations():
    """يُنهي الحجوزات النشطة التي تجاوزت تاريخ انتهائها ويحرر الوحدات.
    تُستدعى عند أي قراءة/إنشاء يتعلق بالحجوزات لضمان عدم بقاء وحدات معلقة."""
    today = datetime.now().date()
    stale = Reservation.query.filter(
        Reservation.status == "active",
        Reservation.expiry_date.isnot(None),
        Reservation.expiry_date < today,
    ).all()
    if not stale:
        return 0
    released = 0
    for r in stale:
        r.status = "expired"
        if db.session.get(RealEstateUnit, r.unit_id):
            # استبعاد هذا الحجز من فحص الاحتكار قبل التحرير
            r.status = "expired"
            others_active = any(
                o.id != r.id and o.status == "active"
                for o in r.unit.reservations) if r.unit else False
            others_alloc = any(
                a.status == "active"
                for a in r.unit.allocations) if r.unit else False
            has_contract = any(
                c.status != "cancelled"
                for c in r.unit.sales_contracts) if r.unit else False
            if not (others_active or others_alloc or has_contract):
                if r.unit.status == "reserved":
                    r.unit.status = "available"
                    released += 1
    db.session.commit()
    _log("auto_expire", "reservation", None,
         f"expired={len(stale)} released={released}")
    return len(stale)


def _create_contract(unit_id, customer_id, data):
    unit = RealEstateUnit.query.get_or_404(unit_id)
    if unit.status == "sold" and not data.get("force"):
        return None, "unit_already_sold"
    total = float(data.get("total_amount") or unit.price or 0)
    discount = float(data.get("discount") or 0)

    # سقف الخصم: فوق الحد يتطلب صلاحية أدمن أو تجاوز صريح (force) — يُسجَّل بالتدقيق
    import utils.settings as settings_module
    from flask import session as _session
    cap = settings_module.get_float("realestate_max_discount_percent", 10) or 0
    if total > 0 and discount > 0:
        pct = discount / total * 100.0
        is_admin = (_session.get("role") == "admin")
        if pct > cap and not is_admin and not data.get("force"):
            return None, "discount_limit_exceeded"

    net = total - discount
    vat_rate = float(data.get("vat_rate")
                     or settings_module.get_float("realestate_vat_percent", 15)
                     or 0)
    vat_amount = round(net * vat_rate / 100.0, 2) if vat_rate else 0.0

    # بوابة الاعتماد: عند تفعيلها يُنشأ العقد بحالة (بانتظار الاعتماد)
    approval = ("pending"
                if str(settings_module.get("realestate_contract_approval", "0")) in ("1", "true", "on")
                else "not_required")

    contract = SalesContract(
        contract_number=data.get("contract_number") or _next_contract_number(),
        unit_id=unit_id,
        customer_id=customer_id or None,
        payment_plan_id=data.get("payment_plan_id") or None,
        total_amount=total,
        discount=discount,
        net_amount=net,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        contract_date=parse_date(data.get("contract_date")) or datetime.now().date(),
        status="active",
        approval_status=approval,
        notes=data.get("notes"),
    )
    db.session.add(contract)
    db.session.flush()
    unit.status = "sold"
    return contract, None


# ============ المباني ============

@re_bp.route("/buildings", methods=["GET"])
@require_api("realestate", "view")
def list_buildings():
    return jsonify([b.to_dict() for b in Building.query.order_by(Building.name).all()])


@re_bp.route("/buildings", methods=["POST"])
@require_api("realestate", "create")
def create_building():
    data = request.get_json() or {}
    building = Building(
        project_id=data.get("project_id") or None,
        code=data.get("code"),
        name=data.get("name"),
        floors_count=int(data.get("floors_count") or 0),
        description=data.get("description"),
    )
    if not building.name:
        return jsonify({"error": "invalid_building"}), 400
    db.session.add(building)
    db.session.commit()
    _log("create", "building", building.id, building.name)
    return jsonify(building.to_dict()), 201


@re_bp.route("/buildings/<int:building_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_building(building_id):
    building = Building.query.get_or_404(building_id)
    data = request.get_json() or {}
    for field in ["project_id", "code", "name", "floors_count", "description"]:
        if field in data:
            setattr(building, field, data[field])
    db.session.commit()
    _log("update", "building", building.id, building.name)
    return jsonify(building.to_dict())


@re_bp.route("/buildings/<int:building_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_building(building_id):
    building = Building.query.get_or_404(building_id)
    if building.units:
        return jsonify({"error": "building_has_units"}), 400
    name = building.name
    db.session.delete(building)
    db.session.commit()
    _log("delete", "building", building_id, name)
    return jsonify({"success": True})


# ============ الطوابق ============

@re_bp.route("/floors", methods=["GET"])
@require_api("realestate", "view")
def list_floors():
    return jsonify([f.to_dict() for f in Floor.query.order_by(Floor.number).all()])


@re_bp.route("/floors", methods=["POST"])
@require_api("realestate", "create")
def create_floor():
    data = request.get_json() or {}
    floor = Floor(
        building_id=data.get("building_id") or None,
        number=int(data.get("number") or 1),
        name=data.get("name"),
        description=data.get("description"),
    )
    db.session.add(floor)
    db.session.commit()
    _log("create", "floor", floor.id, floor.name or str(floor.number))
    return jsonify(floor.to_dict()), 201


@re_bp.route("/floors/<int:floor_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_floor(floor_id):
    floor = Floor.query.get_or_404(floor_id)
    data = request.get_json() or {}
    for field in ["building_id", "number", "name", "description"]:
        if field in data:
            setattr(floor, field, data[field])
    db.session.commit()
    _log("update", "floor", floor.id, floor.name or str(floor.number))
    return jsonify(floor.to_dict())


@re_bp.route("/floors/<int:floor_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_floor(floor_id):
    floor = Floor.query.get_or_404(floor_id)
    if floor.units:
        return jsonify({"error": "floor_has_units"}), 400
    ref = floor.name or str(floor.number)
    db.session.delete(floor)
    db.session.commit()
    _log("delete", "floor", floor_id, ref)
    return jsonify({"success": True})


# ============ أنواع الوحدات ============

@re_bp.route("/unit-types", methods=["GET"])
@require_api("realestate", "view")
def list_unit_types():
    return jsonify([u.to_dict() for u in UnitType.query.order_by(UnitType.name).all()])


@re_bp.route("/unit-types", methods=["POST"])
@require_api("realestate", "create")
def create_unit_type():
    data = request.get_json() or {}
    ut = UnitType(name=data.get("name"), code=data.get("code"), is_active=data.get("is_active", True))
    if not ut.name:
        return jsonify({"error": "invalid_unit_type"}), 400
    db.session.add(ut)
    db.session.commit()
    _log("create", "unit_type", ut.id, ut.name)
    return jsonify(ut.to_dict()), 201


@re_bp.route("/unit-types/<int:type_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_unit_type(type_id):
    ut = UnitType.query.get_or_404(type_id)
    data = request.get_json() or {}
    for field in ["name", "code", "is_active"]:
        if field in data:
            setattr(ut, field, data[field])
    db.session.commit()
    _log("update", "unit_type", ut.id, ut.name)
    return jsonify(ut.to_dict())


@re_bp.route("/unit-types/<int:type_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_unit_type(type_id):
    ut = UnitType.query.get_or_404(type_id)
    if ut.units:
        return jsonify({"error": "unit_type_in_use"}), 400
    name = ut.name
    db.session.delete(ut)
    db.session.commit()
    _log("delete", "unit_type", type_id, name)
    return jsonify({"success": True})


# ============ الملاك ============

@re_bp.route("/owners", methods=["GET"])
@require_api("realestate", "view")
def list_owners():
    return jsonify([o.to_dict() for o in Owner.query.order_by(Owner.full_name).all()])


@re_bp.route("/owners", methods=["POST"])
@require_api("realestate", "create")
def create_owner():
    data = request.get_json() or {}
    owner = Owner(
        full_name=data.get("full_name"),
        id_number=data.get("id_number"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        type=data.get("type", "individual"),
    )
    if not owner.full_name:
        return jsonify({"error": "invalid_owner"}), 400
    db.session.add(owner)
    db.session.commit()
    _log("create", "owner", owner.id, owner.full_name)
    return jsonify(owner.to_dict()), 201


@re_bp.route("/owners/<int:owner_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    data = request.get_json() or {}
    for field in ["full_name", "id_number", "phone", "email", "address", "type"]:
        if field in data:
            setattr(owner, field, data[field])
    db.session.commit()
    _log("update", "owner", owner.id, owner.full_name)
    return jsonify(owner.to_dict())


@re_bp.route("/owners/<int:owner_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    # حراسة مرجعية: مالك لوحدات أو حصص لا يُحذف
    if owner.units:
        return jsonify({"error": "owner_has_units"}), 400
    if owner.shares:
        return jsonify({"error": "owner_has_shares"}), 400
    name = owner.full_name
    db.session.delete(owner)
    db.session.commit()
    _log("delete", "owner", owner_id, name)
    return jsonify({"success": True})


# ============ الحجوزات ============

@re_bp.route("/reservations", methods=["GET"])
@require_api("realestate", "view")
def list_reservations():
    _expire_stale_reservations()
    q = Reservation.query.filter(Reservation.deleted_at.is_(None)).order_by(Reservation.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/reservations", methods=["POST"])
@require_api("realestate", "create")
def create_reservation():
    _expire_stale_reservations()
    data = request.get_json() or {}
    unit = RealEstateUnit.query.get_or_404(data.get("unit_id"))
    if unit.status == "sold":
        return jsonify({"error": "unit_already_sold"}), 400
    # حماية التداخل: لا يجوز أكثر من حجز/تخصيص نشط واحد على نفس الوحدة
    if _unit_has_live_hold(unit):
        return jsonify({"error": "unit_already_reserved"}), 400
    # فحص استادة العميل (KYC): محظور أو مرفوض → رفض
    blocked = _customer_screening_blocked(data.get("customer_id"))
    if blocked:
        return jsonify({"error": blocked}), 400
    _expiry = parse_date(data.get("expiry_date"))
    # تحقق: تاريخ الانتهاء يجب أن يكون مستقبلياً (وإلا يُنشأ حجز ميت فوراً)
    if _expiry and _expiry < datetime.now().date():
        return jsonify({"error": "invalid_expiry_date"}), 400
    reservation = Reservation(
        unit_id=unit.id,
        customer_id=data.get("customer_id") or None,
        reserved_date=parse_date(data.get("reserved_date")) or datetime.now().date(),
        expiry_date=_expiry,
        deposit=float(data.get("deposit") or 0),
        status="active",
        notes=data.get("notes"),
    )
    db.session.add(reservation)
    db.session.flush()
    if unit.status != "reserved":
        unit.status = "reserved"
    db.session.commit()
    _log("create", "reservation", reservation.id, f"unit={unit.unit_code}")
    return jsonify(reservation.to_dict()), 201


@re_bp.route("/reservations/<int:res_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    data = request.get_json() or {}
    old_unit_id = reservation.unit_id

    for field in ["customer_id", "reserved_date", "expiry_date", "deposit", "status", "notes"]:
        if field in data:
            setattr(reservation, field, data[field])

    if "unit_id" in data and data["unit_id"] and data["unit_id"] != old_unit_id:
        new_unit = RealEstateUnit.query.get_or_404(data["unit_id"])
        if new_unit.status == "sold":
            return jsonify({"error": "unit_already_sold"}), 400
        reservation.unit_id = new_unit.id
        if new_unit.status != "reserved":
            new_unit.status = "reserved"

    if reservation.status == "cancelled":
        # تحرير صحيح: فقط إذا لم تبقَ أسباب احتكار أخرى على الوحدة
        _release_unit_if_reserved(reservation.unit_id)

    # إن نُقل الحجز لوحدة أخرى: حرر الوحدة القديمة إن لم يبق عليها احتكار
    if old_unit_id and old_unit_id != reservation.unit_id:
        _release_unit_if_reserved(old_unit_id)

    db.session.commit()
    _log("update", "reservation", res_id, "تحديث حجز")
    return jsonify(reservation.to_dict())


@re_bp.route("/reservations/<int:res_id>/convert", methods=["POST"])
@require_api("realestate", "create")
def convert_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    data = request.get_json() or {}
    if reservation.status != "active":
        return jsonify({"error": "reservation_not_active"}), 400
    contract, err = _create_contract(reservation.unit_id, reservation.customer_id, data)
    if err:
        return jsonify({"error": err}), 400
    reservation.status = "converted"
    reservation.customer_id = contract.customer_id
    # تحميل العربون: يُوثَّق بالعقد ويُخصم تلقائياً من دفعة أولى عند توليد الخطة
    deposit = float(reservation.deposit or 0)
    if deposit > 0:
        note = (contract.notes or "")
        marker = f" | عربون محمّل من حجز #{reservation.id}: {deposit:.2f}"
        if "عربون محمّل" not in note:
            contract.notes = note + marker
    db.session.commit()
    _log("convert", "reservation", res_id, f"contract={contract.contract_number} deposit={deposit}")
    return jsonify({"contract": contract.to_dict()}), 201


@re_bp.route("/reservations/<int:res_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    was_active = (reservation.status == "active")
    unit_id = reservation.unit_id
    # Soft-delete: أرشفة الحجز بدل حذفه — يحفظ السجل التاريخي للوحدة والعميل
    reservation.status = "cancelled"
    from datetime import datetime as _dt
    reservation.deleted_at = _dt.now()
    if was_active:
        _release_unit_if_reserved(unit_id)
    db.session.commit()
    _log("delete", "reservation", res_id, "إلغاء/أرشفة حجز")
    return jsonify({"success": True})


# ============ التخصيص ============

@re_bp.route("/allocations", methods=["GET"])
@require_api("realestate", "view")
def list_allocations():
    q = Allocation.query.order_by(Allocation.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/allocations", methods=["POST"])
@require_api("realestate", "create")
def create_allocation():
    _expire_stale_reservations()
    data = request.get_json() or {}
    unit = RealEstateUnit.query.get_or_404(data.get("unit_id"))
    if unit.status == "sold":
        return jsonify({"error": "unit_already_sold"}), 400
    # حماية التداخل: لا تخصيص نشط فوق حجز/تخصيص قائم
    if _unit_has_live_hold(unit):
        return jsonify({"error": "unit_already_reserved"}), 400
    # فحص استادة العميل (KYC)
    blocked = _customer_screening_blocked(data.get("customer_id"))
    if blocked:
        return jsonify({"error": blocked}), 400
    allocation = Allocation(
        unit_id=unit.id,
        customer_id=data.get("customer_id") or None,
        allocated_date=parse_date(data.get("allocated_date")) or datetime.now().date(),
        status="active",
        notes=data.get("notes"),
    )
    db.session.add(allocation)
    db.session.flush()
    if unit.status != "reserved":
        unit.status = "reserved"
    db.session.commit()
    _log("create", "allocation", allocation.id, f"unit={unit.unit_code}")
    return jsonify(allocation.to_dict()), 201


@re_bp.route("/allocations/<int:alloc_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_allocation(alloc_id):
    allocation = Allocation.query.get_or_404(alloc_id)
    data = request.get_json() or {}
    old_unit_id = allocation.unit_id
    for field in ["customer_id", "allocated_date", "status", "notes"]:
        if field in data:
            setattr(allocation, field, data[field])
    if "unit_id" in data and data["unit_id"] and data["unit_id"] != old_unit_id:
        new_unit = RealEstateUnit.query.get_or_404(data["unit_id"])
        if new_unit.status == "sold":
            return jsonify({"error": "unit_already_sold"}), 400
        allocation.unit_id = new_unit.id
        if new_unit.status != "reserved":
            new_unit.status = "reserved"
    if allocation.status == "cancelled":
        _release_unit_if_reserved(allocation.unit_id)
    if old_unit_id and old_unit_id != allocation.unit_id:
        _release_unit_if_reserved(old_unit_id)
    db.session.commit()
    _log("update", "allocation", alloc_id, "تحديث تخصيص")
    return jsonify(allocation.to_dict())


@re_bp.route("/allocations/<int:alloc_id>/convert", methods=["POST"])
@require_api("realestate", "create")
def convert_allocation(alloc_id):
    allocation = Allocation.query.get_or_404(alloc_id)
    data = request.get_json() or {}
    if allocation.status != "active":
        return jsonify({"error": "allocation_not_active"}), 400
    contract, err = _create_contract(allocation.unit_id, allocation.customer_id, data)
    if err:
        return jsonify({"error": err}), 400
    allocation.status = "converted"
    allocation.customer_id = contract.customer_id
    db.session.commit()
    _log("convert", "allocation", alloc_id, f"contract={contract.contract_number}")
    return jsonify({"contract": contract.to_dict()}), 201


@re_bp.route("/allocations/<int:alloc_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_allocation(alloc_id):
    allocation = Allocation.query.get_or_404(alloc_id)
    was_active = (allocation.status == "active")
    unit_id = allocation.unit_id
    db.session.delete(allocation)
    db.session.flush()
    if was_active:
        _release_unit_if_reserved(unit_id)
    db.session.commit()
    _log("delete", "allocation", alloc_id, "حذف تخصيص")
    return jsonify({"success": True})


# ============ عقود البيع ============

@re_bp.route("/sales-contracts", methods=["GET"])
@require_api("realestate", "view")
def list_sales_contracts():
    q = SalesContract.query.filter(SalesContract.deleted_at.is_(None)).order_by(SalesContract.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/sales-contracts", methods=["POST"])
@require_api("realestate", "create")
def create_sales_contract():
    data = request.get_json() or {}
    unit_id = data.get("unit_id")
    if not unit_id:
        return jsonify({"error": "invalid_contract"}), 400
    contract, err = _create_contract(unit_id, data.get("customer_id"), data)
    if err:
        return jsonify({"error": err}), 400
    db.session.commit()
    _log("create", "sales_contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict()), 201


@re_bp.route("/sales-contracts/<int:contract_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_sales_contract(contract_id):
    contract = SalesContract.query.get_or_404(contract_id)
    data = request.get_json() or {}
    old_unit_id = contract.unit_id
    for field in ["contract_number", "unit_id", "customer_id", "payment_plan_id",
                  "total_amount", "discount", "contract_date", "status", "notes"]:
        if field in data:
            setattr(contract, field, data[field])
    contract.net_amount = float(contract.total_amount or 0) - float(contract.discount or 0)
    import utils.settings as settings_module
    if data.get("vat_rate") is not None:
        contract.vat_rate = float(data.get("vat_rate") or 0)
    vat_rate = float(getattr(contract, "vat_rate", 0) or 0)
    contract.vat_amount = round(contract.net_amount * vat_rate / 100.0, 2) if vat_rate else 0

    if data.get("unit_id") and contract.unit:
        contract.unit.status = "sold"
    # تحرير الوحدة القديمة إن نُقل العقد لوحدة أخرى وبقي بلا عقود سارية
    if old_unit_id and old_unit_id != contract.unit_id:
        old_unit = db.session.get(RealEstateUnit, old_unit_id)
        if old_unit and not any(c.status != "cancelled" for c in old_unit.sales_contracts):
            if not (old_unit.payment_plans and any(
                    p.id != contract.payment_plan_id for p in old_unit.payment_plans)):
                old_unit.status = "available"
    db.session.commit()
    _log("update", "sales_contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@re_bp.route("/sales-contracts/<int:contract_id>/approve", methods=["POST"])
@require_api("realestate", "edit")
def approve_sales_contract(contract_id):
    """اعتماد عقد البيع — للأدمن فقط عند تفعيل بوابة الاعتماد."""
    from flask import session as _session
    if _session.get("role") != "admin":
        return jsonify({"error": "admin_only"}), 403
    contract = SalesContract.query.get_or_404(contract_id)
    contract.approval_status = "approved"
    db.session.commit()
    _log("approve", "sales_contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@re_bp.route("/sales-contracts/<int:contract_id>/cancel", methods=["POST"])
@require_api("realestate", "edit")
def cancel_sales_contract(contract_id):
    contract = SalesContract.query.get_or_404(contract_id)
    if contract.status == "cancelled":
        return jsonify({"error": "already_cancelled"}), 400
    # حماية الرهن: عقد مرهون لبنك لا يُلغى إلا بتسوية أو تجاوز صريح (force)
    active_mortgage = UnitMortgage.query.filter_by(
        unit_id=contract.unit_id, status="active").first() if contract.unit_id else None
    if active_mortgage and not (request.get_json(silent=True) or {}).get("force"):
        return jsonify({"error": "unit_has_active_mortgage",
                        "mortgage_id": active_mortgage.id}), 400
    contract.status = "cancelled"
    unit = contract.unit
    if unit:
        has_other = [c for c in unit.sales_contracts if c.id != contract.id and c.status != "cancelled"]
        has_plan = unit.payment_plans and any(True for p in unit.payment_plans if p.id != contract.payment_plan_id)
        if not has_other and not has_plan:
            unit.status = "available"
    db.session.commit()
    _log("cancel", "sales_contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@re_bp.route("/sales-contracts/<int:contract_id>/generate-plan", methods=["POST"])
@require_api("realestate", "create")
def generate_plan_for_contract(contract_id):
    contract = SalesContract.query.get_or_404(contract_id)
    data = request.get_json() or {}
    total = float(data.get("total_amount") or contract.net_amount or contract.total_amount or 0)
    down = float(data.get("down_payment") or 0)
    months = int(data.get("months") or 1)
    start = parse_date(data.get("start_date")) or datetime.now().date()
    monthly = float(data.get("monthly_amount") or 0)
    if months <= 0:
        return jsonify({"error": "invalid_plan"}), 400
    # العربون المحمّل من حجز مُحوَّل يُخصم تلقائياً من الدفعة الأولى إن لم يُحدَّد غيره
    if not down:
        src_res = (Reservation.query
                   .filter_by(unit_id=contract.unit_id, status="converted")
                   .order_by(Reservation.id.desc()).first())
        if src_res and float(src_res.deposit or 0) > 0:
            down = min(float(src_res.deposit), total)
    if not monthly and total > down:
        monthly = round((total - down) / months, 2)

    plan = PaymentPlan(
        unit_id=contract.unit_id,
        customer_id=contract.customer_id,
        financial_year_id=data.get("financial_year_id") or None,
        total_amount=total,
        down_payment=down,
        monthly_amount=monthly,
        start_date=start,
        months=months,
        status="active",
    )
    db.session.add(plan)
    db.session.flush()

    def add_months(d, n):
        total_m = d.month - 1 + n
        year = d.year + total_m // 12
        month = total_m % 12 + 1
        day = min(d.day, 28)
        return d.replace(year=year, month=month, day=day)

    for n in range(1, months + 1):
        due = add_months(start, n)
        if n == months and total > down:
            last = round(total - down - monthly * (months - 1), 2)
            amount = last if last > 0 else monthly
        else:
            amount = monthly
        db.session.add(Installment(
            plan_id=plan.id,
            installment_number=n,
            amount=amount,
            paid_amount=0,
            due_date=due,
            status="pending",
        ))

    contract.payment_plan_id = plan.id
    _set_unit_status(contract.unit_id, "sold")
    db.session.commit()
    _log("create", "plan", plan.id, f"contract={contract.contract_number}")
    return jsonify(plan.to_dict()), 201


@re_bp.route("/sales-contracts/<int:contract_id>/complete", methods=["POST"])
@require_api("realestate", "edit")
def complete_sales_contract(contract_id):
    contract = SalesContract.query.get_or_404(contract_id)
    if (contract.approval_status or "not_required") == "pending":
        return jsonify({"error": "approval_pending"}), 400
    contract.status = "completed"
    db.session.commit()
    _log("complete", "sales_contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@re_bp.route("/sales-contracts/<int:contract_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_sales_contract(contract_id):
    contract = SalesContract.query.get_or_404(contract_id)
    if contract.commissions or contract.payment_plan:
        return jsonify({"error": "contract_has_commissions"}), 400
    num = contract.contract_number
    # Soft-delete: إلغاء العقد وأرشفته بدل الحذف الفعلي — سجل مالي عقاري
    contract.status = "cancelled"
    from datetime import datetime as _dt
    contract.deleted_at = _dt.now()
    db.session.commit()
    _log("delete", "sales_contract", contract_id, num)
    return jsonify({"success": True})


# ============ العمولات ============

@re_bp.route("/commissions", methods=["GET"])
@require_api("realestate", "view")
def list_commissions():
    q = Commission.query.order_by(Commission.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/commissions", methods=["POST"])
@require_api("realestate", "create")
def create_commission():
    data = request.get_json() or {}
    rate = float(data.get("rate") or 0)
    # تحقق: النسبة بين 0 و 100 حصراً
    if rate < 0 or rate > 100:
        return jsonify({"error": "invalid_rate"}), 400
    amount = data.get("amount")
    if amount in (None, "", 0):
        contract = db.session.get(SalesContract, data.get("contract_id"))
        base = float(contract.net_amount or contract.total_amount or 0) if contract else 0
        amount = round(base * rate / 100, 2) if rate else 0
    commission = Commission(
        contract_id=data.get("contract_id") or None,
        unit_id=data.get("unit_id") or None,
        employee_id=data.get("employee_id") or None,
        broker_id=data.get("broker_id") or None,
        customer_id=data.get("customer_id") or None,
        rate=rate,
        amount=float(amount or 0),
        status="pending",
        due_date=parse_date(data.get("due_date")),
        notes=data.get("notes"),
    )
    db.session.add(commission)
    db.session.commit()
    _log("create", "commission", commission.id, f"amount={commission.amount}")
    return jsonify(commission.to_dict()), 201


@re_bp.route("/commissions/<int:comm_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_commission(comm_id):
    commission = Commission.query.get_or_404(comm_id)
    data = request.get_json() or {}
    if "rate" in data:
        r = float(data.get("rate") or 0)
        if r < 0 or r > 100:
            return jsonify({"error": "invalid_rate"}), 400
    for field in ["contract_id", "unit_id", "employee_id", "broker_id", "customer_id",
                  "rate", "amount", "status", "due_date", "paid_date", "notes"]:
        if field in data:
            setattr(commission, field, data[field])
    db.session.commit()
    _log("update", "commission", comm_id, "تحديث عمولة")
    return jsonify(commission.to_dict())


@re_bp.route("/commissions/<int:comm_id>/pay", methods=["POST"])
@require_api("realestate", "edit")
def pay_commission(comm_id):
    commission = Commission.query.get_or_404(comm_id)
    commission.status = "paid"
    commission.paid_date = datetime.now().date()
    db.session.commit()
    _log("pay", "commission", comm_id, "دفع عمولة")
    return jsonify(commission.to_dict())


@re_bp.route("/commissions/<int:comm_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_commission(comm_id):
    commission = Commission.query.get_or_404(comm_id)
    db.session.delete(commission)
    db.session.commit()
    _log("delete", "commission", comm_id, "حذف عمولة")
    return jsonify({"success": True})


# ============ تسليم الوحدة ============

@re_bp.route("/deliveries", methods=["GET"])
@require_api("realestate", "view")
def list_deliveries():
    q = UnitDelivery.query.order_by(UnitDelivery.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/deliveries", methods=["POST"])
@require_api("realestate", "create")
def create_delivery():
    data = request.get_json() or {}
    delivery = UnitDelivery(
        unit_id=data.get("unit_id"),
        customer_id=data.get("customer_id") or None,
        delivery_date=parse_date(data.get("delivery_date")) or datetime.now().date(),
        status="delivered",
        notes=data.get("notes"),
    )
    db.session.add(delivery)
    db.session.commit()
    _log("create", "delivery", delivery.id, f"unit={delivery.unit.unit_code if delivery.unit else None}")
    return jsonify(delivery.to_dict()), 201


@re_bp.route("/deliveries/<int:delivery_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_delivery(delivery_id):
    delivery = UnitDelivery.query.get_or_404(delivery_id)
    data = request.get_json() or {}
    for field in ["unit_id", "customer_id", "delivery_date", "status", "notes"]:
        if field in data:
            setattr(delivery, field, data[field])
    db.session.commit()
    _log("update", "delivery", delivery_id, "تحديث تسليم")
    return jsonify(delivery.to_dict())


@re_bp.route("/deliveries/<int:delivery_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_delivery(delivery_id):
    delivery = UnitDelivery.query.get_or_404(delivery_id)
    db.session.delete(delivery)
    db.session.commit()
    _log("delete", "delivery", delivery_id, "حذف تسليم")
    return jsonify({"success": True})


# ============ الصيانة ============

@re_bp.route("/maintenance", methods=["GET"])
@require_api("realestate", "view")
def list_maintenance():
    q = MaintenanceRequest.query.order_by(MaintenanceRequest.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/maintenance", methods=["POST"])
@require_api("realestate", "create")
def create_maintenance():
    data = request.get_json() or {}
    req = MaintenanceRequest(
        unit_id=data.get("unit_id"),
        customer_id=data.get("customer_id") or None,
        request_date=parse_date(data.get("request_date")) or datetime.now().date(),
        issue_type=data.get("issue_type"),
        description=data.get("description"),
        status="open",
        cost=float(data.get("cost") or 0),
        assigned_to=data.get("assigned_to") or None,
        notes=data.get("notes"),
    )
    db.session.add(req)
    db.session.commit()
    _log("create", "maintenance", req.id, req.issue_type or "صيانة")
    return jsonify(req.to_dict()), 201


@re_bp.route("/maintenance/<int:req_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_maintenance(req_id):
    req = MaintenanceRequest.query.get_or_404(req_id)
    data = request.get_json() or {}
    for field in ["unit_id", "customer_id", "request_date", "issue_type", "description",
                  "status", "cost", "assigned_to", "resolved_date", "notes"]:
        if field in data:
            setattr(req, field, data[field])
    db.session.commit()
    _log("update", "maintenance", req_id, "تحديث صيانة")
    return jsonify(req.to_dict())


@re_bp.route("/maintenance/<int:req_id>/start", methods=["POST"])
@require_api("realestate", "edit")
def start_maintenance(req_id):
    req = MaintenanceRequest.query.get_or_404(req_id)
    req.status = "in_progress"
    db.session.commit()
    return jsonify(req.to_dict())


@re_bp.route("/maintenance/<int:req_id>/done", methods=["POST"])
@require_api("realestate", "edit")
def done_maintenance(req_id):
    req = MaintenanceRequest.query.get_or_404(req_id)
    data = request.get_json() or {}
    req.status = "done"
    req.resolved_date = parse_date(data.get("resolved_date")) or datetime.now().date()
    if "cost" in data:
        req.cost = float(data.get("cost") or 0)
    db.session.commit()
    _log("done", "maintenance", req_id, "إنجاز صيانة")
    return jsonify(req.to_dict())


@re_bp.route("/maintenance/<int:req_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_maintenance(req_id):
    req = MaintenanceRequest.query.get_or_404(req_id)
    db.session.delete(req)
    db.session.commit()
    _log("delete", "maintenance", req_id, "حذف صيانة")
    return jsonify({"success": True})


# ============ الحصص العقارية ============

@re_bp.route("/shares", methods=["GET"])
@require_api("realestate", "view")
def list_shares():
    q = UnitShare.query.order_by(UnitShare.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


def _shares_total_excluding(unit_id, exclude_id=None):
    from sqlalchemy import func as _func
    q = db.session.query(_func.coalesce(_func.sum(UnitShare.share_percent), 0)).filter(
        UnitShare.unit_id == unit_id)
    if exclude_id:
        q = q.filter(UnitShare.id != exclude_id)
    return float(q.scalar() or 0)


@re_bp.route("/shares", methods=["POST"])
@require_api("realestate", "create")
def create_share():
    data = request.get_json() or {}
    unit_id = data.get("unit_id")
    if not unit_id or not db.session.get(RealEstateUnit, unit_id):
        return jsonify({"error": "invalid_unit"}), 400
    pct = float(data.get("share_percent") or 0)
    if pct <= 0 or pct > 100:
        return jsonify({"error": "invalid_share_percent"}), 400
    if _shares_total_excluding(unit_id) + pct > 100.0:
        return jsonify({"error": "shares_exceed_100"}), 400
    share = UnitShare(
        unit_id=unit_id,
        owner_id=data.get("owner_id"),
        share_percent=pct,
        notes=data.get("notes"),
    )
    db.session.add(share)
    db.session.commit()
    _log("create", "unit_share", share.id, f"unit={share.unit_id}")
    return jsonify(share.to_dict()), 201


@re_bp.route("/shares/<int:share_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_share(share_id):
    share = UnitShare.query.get_or_404(share_id)
    data = request.get_json() or {}
    if "share_percent" in data:
        pct = float(data.get("share_percent") or 0)
        if pct <= 0 or pct > 100:
            return jsonify({"error": "invalid_share_percent"}), 400
        others = _shares_total_excluding(share.unit_id, exclude_id=share.id)
        if others + pct > 100.0:
            return jsonify({"error": "shares_exceed_100"}), 400
    for field in ["unit_id", "owner_id", "share_percent", "notes"]:
        if field in data:
            setattr(share, field, data[field])
    db.session.commit()
    return jsonify(share.to_dict())


@re_bp.route("/shares/<int:share_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_share(share_id):
    share = UnitShare.query.get_or_404(share_id)
    db.session.delete(share)
    db.session.commit()
    return jsonify({"success": True})


# ============ سجل التسعير ============

@re_bp.route("/price-history", methods=["GET"])
@require_api("realestate", "view")
def list_price_history():
    unit_id = request.args.get("unit_id", type=int)
    q = UnitPriceHistory.query.order_by(UnitPriceHistory.id.desc())
    if unit_id:
        q = q.filter_by(unit_id=unit_id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


# ============ توفر الوحدات (Availability) ============

def _customer_screening_blocked(customer_id):
    """يرفض العميل المحظور أو صاحب فحص استادة مرفوض. يعيد مفتاح خطأ أو None."""
    if not customer_id:
        return None
    sc = (TenantScreening.query
          .filter_by(customer_id=customer_id)
          .order_by(TenantScreening.id.desc())
          .first())
    if not sc:
        return None
    if sc.blacklist:
        return "customer_blacklisted"
    if sc.result == "rejected":
        return "screening_rejected"
    return None


@re_bp.route("/units/<int:unit_id>/availability", methods=["GET"])
@require_api("realestate", "view")
def unit_availability(unit_id):
    """حالة توفّر الوحدة: الحجوزات والتخصيصات النشطة والعقود السارية."""
    _expire_stale_reservations()
    unit = RealEstateUnit.query.get_or_404(unit_id)
    active_reservations = [r.to_dict() for r in unit.reservations if r.status == "active"]
    active_allocations = [a.to_dict() for a in unit.allocations if a.status == "active"]
    live_contracts = [c.to_dict() for c in unit.sales_contracts if c.status != "cancelled"]
    return jsonify({
        "unit_id": unit.id,
        "unit_code": unit.unit_code,
        "status": unit.status,
        "is_available": (unit.status == "available" and not _unit_has_live_hold(unit)),
        "active_reservations": active_reservations,
        "active_allocations": active_allocations,
        "live_contracts": live_contracts,
    })


# ============ السماسرة العقارية ============

@re_bp.route("/brokers", methods=["GET"])
@require_api("realestate", "view")
def list_brokers():
    q = Broker.query.order_by(Broker.name)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/brokers", methods=["POST"])
@require_api("realestate", "create")
def create_broker():
    data = request.get_json() or {}
    broker = Broker(
        name=data.get("name"),
        agency_name=data.get("agency_name"),
        phone=data.get("phone"),
        email=data.get("email"),
        id_number=data.get("id_number"),
        default_rate=float(data.get("default_rate") or 0),
        is_active=data.get("is_active", True),
        notes=data.get("notes"),
    )
    if not broker.name:
        return jsonify({"error": "invalid_broker"}), 400
    if broker.default_rate < 0 or broker.default_rate > 100:
        return jsonify({"error": "invalid_rate"}), 400
    db.session.add(broker)
    db.session.commit()
    _log("create", "broker", broker.id, broker.name)
    return jsonify(broker.to_dict()), 201


@re_bp.route("/brokers/<int:broker_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_broker(broker_id):
    broker = Broker.query.get_or_404(broker_id)
    data = request.get_json() or {}
    if "default_rate" in data:
        r = float(data.get("default_rate") or 0)
        if r < 0 or r > 100:
            return jsonify({"error": "invalid_rate"}), 400
    for field in ["name", "agency_name", "phone", "email", "id_number",
                  "default_rate", "is_active", "notes"]:
        if field in data:
            setattr(broker, field, data[field])
    db.session.commit()
    _log("update", "broker", broker.id, broker.name)
    return jsonify(broker.to_dict())


@re_bp.route("/brokers/<int:broker_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_broker(broker_id):
    broker = Broker.query.get_or_404(broker_id)
    if broker.commissions:
        # لديه عمولات مرتبطة: يُعطَّل بدلاً من الحذف حفاظاً على المرجعية
        broker.is_active = False
        db.session.commit()
        _log("deactivate", "broker", broker.id, broker.name)
        return jsonify({"success": True, "deactivated": True})
    name = broker.name
    db.session.delete(broker)
    db.session.commit()
    _log("delete", "broker", broker_id, name)
    return jsonify({"success": True})


# ============ التسليم الاحترافي (Snagging) ============

@re_bp.route("/deliveries/<int:delivery_id>/items", methods=["GET"])
@require_api("realestate", "view")
def list_checklist(delivery_id):
    if not db.session.get(UnitDelivery, delivery_id):
        return jsonify({"error": "delivery_not_found"}), 404
    items = (DeliveryChecklistItem.query.filter_by(delivery_id=delivery_id)
             .order_by(DeliveryChecklistItem.id).all())
    return jsonify([i.to_dict() for i in items])


@re_bp.route("/deliveries/<int:delivery_id>/items", methods=["POST"])
@require_api("realestate", "create")
def add_checklist_item(delivery_id):
    if not db.session.get(UnitDelivery, delivery_id):
        return jsonify({"error": "delivery_not_found"}), 404
    data = request.get_json() or {}
    desc = (data.get("description") or "").strip()
    if not desc:
        return jsonify({"error": "invalid_item"}), 400
    item = DeliveryChecklistItem(
        delivery_id=delivery_id,
        description=desc,
        status="pending" if data.get("status") not in ("ok", "issue", "fixed") else data["status"],
        notes=data.get("notes"),
    )
    db.session.add(item)
    db.session.commit()
    _log("create", "checklist_item", item.id, f"delivery={delivery_id}")
    return jsonify(item.to_dict()), 201


@re_bp.route("/checklist/<int:item_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_checklist_item(item_id):
    item = DeliveryChecklistItem.query.get_or_404(item_id)
    data = request.get_json() or {}
    if "status" in data and data["status"] not in ("pending", "ok", "issue", "fixed"):
        return jsonify({"error": "invalid_status"}), 400
    for field in ["description", "status", "notes"]:
        if field in data:
            setattr(item, field, data[field])
    db.session.commit()
    _log("update", "checklist_item", item.id, f"status={item.status}")
    return jsonify(item.to_dict())


@re_bp.route("/checklist/<int:item_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_checklist_item(item_id):
    item = DeliveryChecklistItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True})


@re_bp.route("/deliveries/<int:delivery_id>/complete", methods=["POST"])
@require_api("realestate", "edit")
def complete_delivery_with_checklist(delivery_id):
    """إتمام التسليم: لا يُقبل وجود بنود معلقة أو أعطال غير مُصلحة."""
    delivery = UnitDelivery.query.get_or_404(delivery_id)
    items = list(delivery.checklist or [])
    if items:
        pending = [i for i in items if i.status in ("pending", "issue")]
        if pending:
            return jsonify({
                "error": "checklist_incomplete",
                "open_items": [i.to_dict() for i in pending],
            }), 400
    delivery.status = "delivered"
    if not delivery.delivery_date:
        delivery.delivery_date = datetime.now().date()
    db.session.commit()
    _log("complete", "delivery", delivery.id, f"items={len(items)}")
    return jsonify(delivery.to_dict())


# ============ فحص الاستادة (Tenant Screening / KYC) ============

@re_bp.route("/screenings", methods=["GET"])
@require_api("realestate", "view")
def list_screenings():
    customer_id = request.args.get("customer_id", type=int)
    q = TenantScreening.query.order_by(TenantScreening.id.desc())
    if customer_id:
        q = q.filter_by(customer_id=customer_id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/screenings", methods=["POST"])
@require_api("realestate", "create")
def create_screening():
    from flask import session as _session
    data = request.get_json() or {}
    cid = data.get("customer_id")
    if not cid or not db.session.get(Customer, cid):
        return jsonify({"error": "invalid_customer"}), 400
    result = data.get("result") or "pending"
    if result not in ("approved", "rejected", "pending"):
        return jsonify({"error": "invalid_result"}), 400
    credit = data.get("credit_status") or "unknown"
    if credit not in ("good", "fair", "bad", "unknown"):
        return jsonify({"error": "invalid_credit_status"}), 400
    sc = TenantScreening(
        customer_id=cid,
        monthly_income=float(data.get("monthly_income") or 0),
        employer=(data.get("employer") or "").strip() or None,
        credit_status=credit,
        blacklist=bool(data.get("blacklist")),
        result=result,
        notes=data.get("notes"),
        checked_by=_session.get("user_id"),
    )
    # قاعدة آلية: قائمة سوداء أو ائتمان سيئ ⇒ مرفوض ما لم يحدد الموظف غير ذلك
    if sc.blacklist or credit == "bad":
        sc.result = "rejected"
    db.session.add(sc)
    db.session.commit()
    _log("create", "screening", sc.id,
         f"customer={cid} result={sc.result} blacklist={sc.blacklist}")
    return jsonify(sc.to_dict()), 201


@re_bp.route("/screenings/<int:sc_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_screening(sc_id):
    sc = TenantScreening.query.get_or_404(sc_id)
    db.session.delete(sc)
    db.session.commit()
    return jsonify({"success": True})


# ============ الرهون العقارية والتمويل ============

@re_bp.route("/mortgages", methods=["GET"])
@require_api("realestate", "view")
def list_mortgages():
    q = UnitMortgage.query.order_by(UnitMortgage.id.desc())
    unit_id = request.args.get("unit_id", type=int)
    status = request.args.get("status")
    if unit_id:
        q = q.filter_by(unit_id=unit_id)
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@re_bp.route("/mortgages", methods=["POST"])
@require_api("realestate", "create")
def create_mortgage():
    data = request.get_json() or {}
    uid = data.get("unit_id")
    if not uid or not db.session.get(RealEstateUnit, uid):
        return jsonify({"error": "invalid_unit"}), 400
    lender = (data.get("lender_name") or "").strip()
    if not lender:
        return jsonify({"error": "lender_required"}), 400
    loan = float(data.get("loan_amount") or 0)
    if loan <= 0:
        return jsonify({"error": "invalid_loan_amount"}), 400
    ltv = float(data.get("ltv_percent") or 0)
    if ltv < 0 or ltv > 100:
        return jsonify({"error": "invalid_ltv"}), 400
    # رهن نشط واحد لكل وحدة
    existing = UnitMortgage.query.filter_by(unit_id=uid, status="active").first()
    if existing:
        return jsonify({"error": "unit_already_mortgaged",
                        "mortgage_id": existing.id}), 400
    m = UnitMortgage(
        unit_id=uid,
        sales_contract_id=data.get("sales_contract_id") or None,
        lender_name=lender,
        loan_amount=loan,
        ltv_percent=ltv,
        interest_rate=float(data.get("interest_rate") or 0),
        start_date=parse_date(data.get("start_date")) or datetime.now().date(),
        end_date=parse_date(data.get("end_date")),
        lien_number=(data.get("lien_number") or "").strip() or None,
        status="active",
        notes=data.get("notes"),
    )
    db.session.add(m)
    db.session.commit()
    _log("create", "mortgage", m.id, f"{lender} loan={loan}")
    return jsonify(m.to_dict()), 201


@re_bp.route("/mortgages/<int:m_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_mortgage(m_id):
    m = UnitMortgage.query.get_or_404(m_id)
    data = request.get_json() or {}
    if "status" in data and data["status"] not in ("active", "settled", "defaulted"):
        return jsonify({"error": "invalid_status"}), 400
    for field in ["lender_name", "loan_amount", "ltv_percent", "interest_rate",
                  "start_date", "end_date", "lien_number", "status", "notes"]:
        if field in data:
            if field == "start_date":
                m.start_date = parse_date(data[field]) or m.start_date
            elif field == "end_date":
                m.end_date = parse_date(data[field])
            elif field == "loan_amount":
                v = float(data[field] or 0)
                if v <= 0:
                    return jsonify({"error": "invalid_loan_amount"}), 400
                m.loan_amount = v
            else:
                setattr(m, field, data[field])
    db.session.commit()
    _log("update", "mortgage", m.id, f"status={m.status}")
    return jsonify(m.to_dict())


@re_bp.route("/mortgages/<int:m_id>/settle", methods=["POST"])
@require_api("realestate", "edit")
def settle_mortgage(m_id):
    """تسوية/رفع الرهن من الوحدة."""
    m = UnitMortgage.query.get_or_404(m_id)
    m.status = "settled"
    db.session.commit()
    _log("settle", "mortgage", m.id, m.lender_name)
    return jsonify(m.to_dict())


@re_bp.route("/mortgages/<int:m_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_mortgage(m_id):
    m = UnitMortgage.query.get_or_404(m_id)
    if m.status == "active":
        return jsonify({"error": "mortgage_active_settle_first"}), 400
    db.session.delete(m)
    db.session.commit()
    return jsonify({"success": True})


# ============ توزيع إيرادات الملكية الجزئية ============

@re_bp.route("/units/<int:unit_id>/distribute-revenue", methods=["POST"])
@require_api("realestate", "edit")
def distribute_unit_revenue(unit_id):
    """يوزع مبلغاً على ملاك الوحدة بحسب حصصهم المسجلة.
    يشترط اكتمال الحصص إلى 100% قبل أي توزيع."""
    unit = RealEstateUnit.query.get_or_404(unit_id)
    data = request.get_json(silent=True) or {}
    amount = float(data.get("amount") or 0)
    if amount <= 0:
        return jsonify({"error": "invalid_amount"}), 400
    shares = sorted(unit.shares, key=lambda s: s.id)
    total_pct = sum(float(s.share_percent or 0) for s in shares)
    if not shares:
        return jsonify({"error": "no_shares_defined"}), 400
    if round(total_pct, 2) != 100.00:
        return jsonify({"error": "shares_do_not_sum_100", "total_percent": round(total_pct, 2)}), 400
    rows, distributed = [], 0.0
    for idx, s in enumerate(shares):
        pct = float(s.share_percent or 0)
        if idx == len(shares) - 1:
            part = round(amount - distributed, 2)  # آخر مالك يمتص فرق التقريب
        else:
            part = round(amount * pct / 100.0, 2)
            distributed += part
        rows.append({
            "owner_id": s.owner_id,
            "owner_name": s.owner.full_name if s.owner else None,
            "share_percent": pct,
            "amount": part,
        })
    _log("distribute", "unit_revenue", unit.id,
         f"amount={amount} owners={len(rows)} ref={data.get('description') or ''}")
    return jsonify({
        "unit_id": unit.id,
        "unit_code": unit.unit_code,
        "amount": amount,
        "distribution": rows,
        "total_distributed": round(sum(r['amount'] for r in rows), 2),
    })


# ============ تحليلات الإشغال والشواغر ============

@re_bp.route("/analytics/occupancy", methods=["GET"])
@require_api("realestate", "view")
def occupancy_analytics():
    """لوحة تحليلات: نسب الإشغال والشواغر إجمالاً ولكل مشروع."""
    def _stats(q):
        total = q.count()
        by = {}
        for st in ("available", "reserved", "sold", "rented"):
            by[st] = q.filter(RealEstateUnit.status == st).count()
        occupied = by.get("sold", 0) + by.get("rented", 0)
        held = occupied + by.get("reserved", 0)
        return {
            "total_units": total,
            **{f"{k}_units": v for k, v in by.items()},
            "occupied_units": occupied,
            "occupancy_rate": round(occupied * 100.0 / total, 2) if total else 0.0,
            "utilization_rate": round(held * 100.0 / total, 2) if total else 0.0,
            "vacancy_rate": round(by.get("available", 0) * 100.0 / total, 2) if total else 0.0,
        }

    base_q = RealEstateUnit.query
    project_id = request.args.get("project_id", type=int)
    if project_id:
        base_q = base_q.filter(RealEstateUnit.project_id == project_id)
    overall = _stats(base_q)

    project_ids = [r[0] for r in
                   db.session.query(RealEstateUnit.project_id).distinct().all()]
    per_project = []
    for p_id in project_ids:
        st = _stats(RealEstateUnit.query.filter(RealEstateUnit.project_id == p_id))
        proj = None
        if p_id:
            from models import Project as _P
            proj = db.session.get(_P, p_id)
        per_project.append({
            "project_id": p_id,
            "project_name": proj.name if proj else None,
            "total_units": st["total_units"],
            "occupied_units": st["occupied_units"],
            "occupancy_rate": st["occupancy_rate"],
        })
    per_project.sort(key=lambda x: -(x["total_units"] or 0))

    mortgaged = UnitMortgage.query.filter_by(status="active").count()
    active_contracts = SalesContract.query.filter(SalesContract.status != "cancelled").count()

    return jsonify({
        "overall": overall,
        "per_project": per_project,
        "active_mortgages": mortgaged,
        "live_sales_contracts": active_contracts,
    })
