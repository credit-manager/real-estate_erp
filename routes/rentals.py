from flask import Blueprint, render_template, request, jsonify
from datetime import date, timedelta
from database import db
from models import (
    RentalContract, RentalRenewal, RentalPayment,
    Customer, RealEstateUnit,
)
from permissions import require_api, require_page

rental_bp = Blueprint("rental", __name__, url_prefix="/api/rentals")
rental_pages_bp = Blueprint("rental_pages", __name__)


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    from auditlog import log_action
    log_action(action, entity, entity_id, description)


def _next_number(prefix, model):
    from utils.docnum import seq_after_max
    return seq_after_max(model, prefix + "-{n:04d}")


def _contract_paid(contract):
    total = db.session.query(db.func.coalesce(db.func.sum(RentalPayment.amount), 0)).filter(
        RentalPayment.contract_id == contract.id
    ).scalar() or 0
    return float(total)


def _contract_due(contract):
    """الاستحقاق المستحق على العقد حتى اليوم (إيجار شهري × أشهر من البداية حتى اليوم/النهاية)."""
    if not contract.start_date:
        return 0.0
    end = contract.end_date or date.today()
    days = (end - contract.start_date).days
    months = max(1, (days + 29) // 30) if days > 0 else 0
    return months * float(contract.monthly_rent or 0)


# ============ صفحات (Pages) ============

@rental_pages_bp.route("/rentals/tenants")
@require_page("rentals")
def tenants_page():
    return render_template("rental_tenants.html")


@rental_pages_bp.route("/rentals/renewals")
@require_page("rentals")
def renewals_page():
    return render_template("rental_renewals.html")


@rental_pages_bp.route("/rentals/collections")
@require_page("rentals")
def collections_page():
    return render_template("rental_collections.html")


@rental_pages_bp.route("/rentals/notifications")
@require_page("rentals")
def notifications_page():
    return render_template("rental_notifications.html")


# ============ المستأجرون (Tenants) ============

@rental_bp.route("/tenants", methods=["GET"])
@require_api("rentals", "view")
def list_tenants():
    """قائمة المستأجرين (العملاء المرتبطين بعقود إيجار) مع إحصائياتهم."""
    customers = Customer.query.order_by(Customer.full_name).all()
    result = []
    for c in customers:
        contracts = RentalContract.query.filter_by(customer_id=c.id).all()
        active = [x for x in contracts if x.status == "active"]
        result.append({
            "id": c.id,
            "full_name": c.full_name,
            "phone": c.phone,
            "email": c.email,
            "address": c.address,
            "type": c.type or "individual",
            "company": c.company,
            "is_active": bool(c.is_active if c.is_active is not None else True),
            "contracts_count": len(contracts),
            "active_contracts": len(active),
            "monthly_total": round(sum(float(x.monthly_rent or 0) for x in active), 2),
            "units": [x.unit.unit_code for x in contracts if x.unit],
        })
    return jsonify(result)


@rental_bp.route("/tenants", methods=["POST"])
@require_api("rentals", "create")
def create_tenant():
    data = request.get_json() or {}
    if not data.get("full_name"):
        return jsonify({"message": "rentals.nameRequired", "error_key": "rentals.nameRequired"}), 400
    customer = Customer(
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        type=data.get("type", "individual"),
        company=data.get("company"),
        notes=data.get("notes"),
        is_active=data.get("is_active", True),
    )
    db.session.add(customer)
    db.session.commit()
    _log("create", "tenant", customer.id, customer.full_name)
    return jsonify(customer.to_dict()), 201


@rental_bp.route("/tenants/<int:tenant_id>", methods=["PUT"])
@require_api("rentals", "edit")
def update_tenant(tenant_id):
    customer = Customer.query.get_or_404(tenant_id)
    data = request.get_json() or {}
    for field in ["full_name", "phone", "email", "address", "type", "company", "notes", "is_active"]:
        if field in data:
            setattr(customer, field, data[field])
    db.session.commit()
    _log("update", "tenant", customer.id, customer.full_name)
    return jsonify(customer.to_dict())


@rental_bp.route("/tenants/<int:tenant_id>", methods=["DELETE"])
@require_api("rentals", "delete")
def delete_tenant(tenant_id):
    customer = Customer.query.get_or_404(tenant_id)
    contracts = RentalContract.query.filter_by(customer_id=tenant_id).count()
    if contracts:
        return jsonify({"message": "rentals.tenantHasContracts", "error_key": "rentals.tenantHasContracts"}), 400
    name = customer.full_name
    db.session.delete(customer)
    db.session.commit()
    _log("delete", "tenant", tenant_id, name)
    return jsonify({"success": True})


# ============ تجديد العقود (Renewals) ============

@rental_bp.route("/renewals", methods=["GET"])
@require_api("rentals", "view")
def list_renewals():
    renewals = RentalRenewal.query.order_by(RentalRenewal.created_at.desc()).all()
    return jsonify([r.to_dict() for r in renewals])


@rental_bp.route("/renewals", methods=["POST"])
@require_api("rentals", "create")
def create_renewal():
    data = request.get_json() or {}
    contract = db.session.get(RentalContract, data.get("contract_id"))
    if not contract:
        return jsonify({"message": "rentals.contractNotFound", "error_key": "rentals.contractNotFound"}), 400
    new_end = _parse_date(data.get("new_end_date"))
    if not new_end:
        return jsonify({"message": "rentals.endDateRequired", "error_key": "rentals.endDateRequired"}), 400

    # التصعيد الإيجاري الآلي: إن لم يُحدَّد إيجار جديد وفعّل المالك التصعيد
    # يُطبَّق النسبة السنوية على الإيجار السابق تلقائياً.
    escalation_applied = 0.0
    import utils.settings as settings_module
    if data.get("new_monthly_rent") in (None, "", 0):
        prev_rent = float(contract.monthly_rent or 0)
        enabled = str(settings_module.get("rental_escalation_enabled", "0")) in ("1", "true", "on")
        pct = settings_module.get_float("rental_escalation_percent", 5) or 0
        if enabled and pct > 0 and prev_rent > 0:
            new_rent = round(prev_rent * (1 + pct / 100.0), 2)
            escalation_applied = pct
        else:
            new_rent = prev_rent
    else:
        new_rent = float(data.get("new_monthly_rent") or contract.monthly_rent or 0)

    renewal = RentalRenewal(
        renewal_number=_next_number("REN", RentalRenewal),
        contract_id=contract.id,
        financial_year_id=data.get("financial_year_id") or contract.financial_year_id,
        previous_end_date=contract.end_date,
        new_end_date=new_end,
        previous_monthly_rent=float(contract.monthly_rent or 0),
        new_monthly_rent=new_rent,
        notes=data.get("notes"),
    )
    db.session.add(renewal)
    contract.end_date = new_end
    contract.monthly_rent = new_rent
    if contract.status == "expired":
        contract.status = "active"
    db.session.commit()
    from utils import accounting as acct
    try:
        acct.post_contract_entries(contract)
    except Exception:
        db.session.rollback()
        return jsonify({"message": "accounting.failed"}), 500
    _log("create", "renewal", renewal.id, renewal.renewal_number)
    out = renewal.to_dict()
    if escalation_applied:
        out["escalation_applied_percent"] = escalation_applied
    return jsonify(out), 201


@rental_bp.route("/renewals/<int:renewal_id>", methods=["DELETE"])
@require_api("rentals", "delete")
def delete_renewal(renewal_id):
    renewal = RentalRenewal.query.get_or_404(renewal_id)
    num = renewal.renewal_number
    db.session.delete(renewal)
    db.session.commit()
    _log("delete", "renewal", renewal_id, num)
    return jsonify({"success": True})


@rental_bp.route("/escalation-config", methods=["GET"])
@require_api("rentals", "view")
def escalation_config():
    """إعدادات التصعيد الآلي لواجهة التجديدات."""
    import utils.settings as settings_module
    enabled = str(settings_module.get("rental_escalation_enabled", "0")) in ("1", "true", "on")
    pct = settings_module.get_float("rental_escalation_percent", 5) or 0
    return jsonify({"enabled": enabled, "percent": pct})


# ============ التحصيل (Collections) ============

@rental_bp.route("/payments", methods=["GET"])
@require_api("rentals", "view")
def list_payments():
    q = RentalPayment.query
    contract_id = request.args.get("contract_id", type=int)
    if contract_id:
        q = q.filter_by(contract_id=contract_id)
    payments = q.order_by(RentalPayment.payment_date.desc()).all()
    return jsonify([p.to_dict() for p in payments])


@rental_bp.route("/payments", methods=["POST"])
@require_api("rentals", "create")
def create_payment():
    data = request.get_json() or {}
    contract = db.session.get(RentalContract, data.get("contract_id"))
    if not contract:
        return jsonify({"message": "rentals.contractNotFound", "error_key": "rentals.contractNotFound"}), 400
    amount = float(data.get("amount") or 0)
    if amount <= 0:
        return jsonify({"message": "rentals.amountRequired", "error_key": "rentals.amountRequired"}), 400
    payment = RentalPayment(
        payment_number=_next_number("COL", RentalPayment),
        contract_id=contract.id,
        financial_year_id=data.get("financial_year_id") or contract.financial_year_id,
        amount=amount,
        payment_date=_parse_date(data.get("payment_date")) or date.today(),
        method=data.get("method", "cash"),
        reference=data.get("reference"),
        notes=data.get("notes"),
    )
    db.session.add(payment)
    db.session.commit()
    from utils import accounting as acct
    try:
        acct.post_payment_entries(
            "rental", "rental_payment", payment.id, amount,
            date=payment.payment_date,
            financial_year_id=payment.financial_year_id,
            is_receipt=True,
            description=f"تحصيل إيجار {contract.contract_number}",
        )
    except Exception:
        db.session.rollback()
        db.session.delete(payment)
        db.session.commit()
        return jsonify({"message": "accounting.failed"}), 500
    _log("create", "payment", payment.id, payment.payment_number)
    return jsonify(payment.to_dict()), 201


@rental_bp.route("/payments/<int:payment_id>", methods=["PUT"])
@require_api("rentals", "edit")
def update_payment(payment_id):
    payment = RentalPayment.query.get_or_404(payment_id)
    data = request.get_json() or {}
    if "amount" in data:
        payment.amount = float(data["amount"] or 0)
    for field in ["method", "reference", "notes", "payment_date"]:
        if field in data:
            if field == "payment_date":
                payment.payment_date = _parse_date(data[field])
            else:
                setattr(payment, field, data[field])
    db.session.commit()
    from utils import accounting as acct
    try:
        # حذف القيد القديم أولاً لمنع تكرار الترحيل عند كل تعديل
        acct.delete_source_entries("rental", "rental_payment", payment.id)
        acct.post_payment_entries(
            "rental", "rental_payment", payment.id, float(payment.amount or 0),
            date=payment.payment_date,
            financial_year_id=payment.financial_year_id,
            is_receipt=True,
            description=f"تحصيل إيجار {payment.contract.contract_number if payment.contract else ''}",
        )
    except Exception:
        db.session.rollback()
        return jsonify({"message": "accounting.failed"}), 500
    _log("update", "payment", payment.id, payment.payment_number)
    return jsonify(payment.to_dict())


@rental_bp.route("/payments/<int:payment_id>", methods=["DELETE"])
@require_api("rentals", "delete")
def delete_payment(payment_id):
    payment = RentalPayment.query.get_or_404(payment_id)
    num = payment.payment_number
    from utils import accounting as acct
    acct.delete_source_entries("rental", "rental_payment", payment_id)
    db.session.delete(payment)
    db.session.commit()
    _log("delete", "payment", payment_id, num)
    return jsonify({"success": True})


# ============ إشعارات (Notifications) ============

@rental_bp.route("/notifications", methods=["GET"])
@require_api("rentals", "view")
def notifications():
    today = date.today()
    soon = today + timedelta(days=30)
    items = []

    # عقود تنتهي قريباً خلال 30 يوم
    expiring = RentalContract.query.filter(
        RentalContract.status == "active",
        RentalContract.end_date.isnot(None),
        RentalContract.end_date >= today,
        RentalContract.end_date <= soon,
    ).all()
    for c in expiring:
        items.append({
            "id": f"expiring-{c.id}",
            "type": "expiring",
            "severity": "warning",
            "title": "rentals.notifExpiring",
            "contract_id": c.id,
            "contract_number": c.contract_number,
            "customer_name": c.customer.full_name if c.customer else None,
            "unit_code": c.unit.unit_code if c.unit else None,
            "end_date": c.end_date.isoformat(),
            "days_left": (c.end_date - today).days,
            "message": "rentals.notifExpiringMsg",
        })

    # عقود منتهية لم تُفعّل (status لا يزال active) مع تاريخ نهاية أقل من اليوم
    expired = RentalContract.query.filter(
        RentalContract.status == "active",
        RentalContract.end_date.isnot(None),
        RentalContract.end_date < today,
    ).all()
    for c in expired:
        items.append({
            "id": f"expired-{c.id}",
            "type": "expired",
            "severity": "danger",
            "title": "rentals.notifExpired",
            "contract_id": c.id,
            "contract_number": c.contract_number,
            "customer_name": c.customer.full_name if c.customer else None,
            "unit_code": c.unit.unit_code if c.unit else None,
            "end_date": c.end_date.isoformat(),
            "days_overdue": (today - c.end_date).days,
            "message": "rentals.notifExpiredMsg",
        })

    # عقود نشطة بها استحقاق متأخر (مدفوع < مستحق حتى اليوم)
    active = RentalContract.query.filter(
        RentalContract.status == "active",
        RentalContract.start_date.isnot(None),
    ).all()
    for c in active:
        paid = _contract_paid(c)
        due = _contract_due(c)
        if due > paid + 0.01:
            items.append({
                "id": f"due-{c.id}",
                "type": "overdue",
                "severity": "info",
                "title": "rentals.notifOverdue",
                "contract_id": c.id,
                "contract_number": c.contract_number,
                "customer_name": c.customer.full_name if c.customer else None,
                "unit_code": c.unit.unit_code if c.unit else None,
                "due": round(due, 2),
                "paid": round(paid, 2),
                "balance": round(due - paid, 2),
                "message": "rentals.notifOverdueMsg",
            })

    items.sort(key=lambda x: 0 if x["severity"] == "danger" else (1 if x["severity"] == "warning" else 2))
    return jsonify(items)
