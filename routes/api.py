from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime, timedelta
from database import db
from models import (
    Project, RealEstateUnit, Employee, Customer, Supplier,
    Invoice, InvoiceItem, PurchaseOrder, PurchaseOrderItem, RentalContract,
    SalesOrder, SalesReturn,
    PaymentPlan, Installment, AuditLog,
)
from permissions import require_api, require_api_any, require_any_view
from routes.financial_years import financial_year_error
from utils.pagination import paged_or_cap

api_bp = Blueprint("api", __name__, url_prefix="/api")


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


def _resolve_financial_year(data):
    """يقرأ السنة المالية من الطلب ويرفض المقفلة."""
    fy_id = data.get("financial_year_id")
    if fy_id in (None, "", 0):
        return None, None
    err = financial_year_error(fy_id)
    if err:
        return None, err
    return fy_id, None


def _guard_financial_year(current_fy_id, new_fy_id):
    """يمنع تعديل مستند يخص سنة مقفلة، أو تحويله إلى سنة مقفلة."""
    err = financial_year_error(new_fy_id)
    if err:
        return err
    if current_fy_id and financial_year_error(current_fy_id):
        return "financialYears.closed"
    return None


def _guard_closed_year(financial_year_id):
    """يمنع حذف مستند يخص سنة مقفلة."""
    if financial_year_id and financial_year_error(financial_year_id):
        return "financialYears.closed"
    return None


# ============ لوحة التحكم ============

@api_bp.route("/dashboard/stats")
@require_api("dashboard", "view")
def dashboard_stats():
    balance = lambda i: float((i.amount or 0) - (i.paid_amount or 0))

    sales = Invoice.query.filter_by(invoice_type="sales").all()
    purchases = Invoice.query.filter_by(invoice_type="purchase").all()
    rentals = RentalContract.query.filter_by(status="active").all()
    installments = Installment.query.all()
    pending_inst = [
        i for i in installments
        if i.status in ("pending", "partial") and balance(i) > 0
    ]

    today = datetime.now()
    keys = []
    y, m = today.year, today.month
    for _ in range(12):
        keys.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()
    trend = {k: {"revenue": 0.0, "expenses": 0.0} for k in keys}
    for inv in Invoice.query.all():
        d = inv.issue_date or (inv.created_at.date() if inv.created_at else None)
        if not d:
            continue
        k = (d.year, d.month)
        if k not in trend:
            continue
        amt = float(inv.amount or 0)
        if inv.invoice_type == "sales":
            trend[k]["revenue"] += amt
        else:
            trend[k]["expenses"] += amt

    statuses = ["active", "finishing", "completed", "suspended"]
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    from models import ApprovalRequest
    from utils.workflow import user_is_approver
    my_role = session.get("role", "")
    pending_reqs = [r for r in ApprovalRequest.query.filter_by(
        status="pending").all() if user_is_approver(r)]

    return jsonify({
        "projects_count": Project.query.count(),
        "active_projects": Project.query.filter_by(status="active").count(),
        "units_count": RealEstateUnit.query.count(),
        "units_available": RealEstateUnit.query.filter_by(status="available").count(),
        "employees_count": Employee.query.filter_by(status="active").count(),
        "customers_count": Customer.query.count(),
        "suppliers_count": Supplier.query.count(),
        "total_revenue": sum(float(i.amount or 0) for i in sales),
        "total_expenses": sum(float(i.amount or 0) for i in purchases),
        "pending_revenue": sum(balance(i) for i in sales),
        "pending_expenses": sum(balance(i) for i in purchases),
        "pending_installments_count": len(pending_inst),
        "pending_installments_amount": sum(balance(i) for i in pending_inst),
        "active_rentals_count": len(rentals),
        "active_rentals_revenue": sum(float(r.monthly_rent or 0) for r in rentals),
        "pending_purchase_orders": PurchaseOrder.query.filter_by(status="pending").count(),
        "pending_approvals_count": len(pending_reqs),
        "revenue_trend": [
            {"month": f"{y}-{m:02d}", **v} for (y, m), v in trend.items()
        ],
        "project_statuses": {
            s: Project.query.filter_by(status=s).count() for s in statuses
        },
        "recent_activity": [l.to_dict() for l in logs],
    })


# ============ الوحدات العقارية ============

@api_bp.route("/units", methods=["GET"])
@require_api("realestate", "view")
def list_units():
    q = RealEstateUnit.query
    status = request.args.get("status")
    project_id = request.args.get("project_id", type=int)
    search = request.args.get("search", "").strip()
    if status:
        q = q.filter_by(status=status)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if search:
        q = q.filter(RealEstateUnit.unit_code.ilike("%" + search + "%"))
    items, envelope = paged_or_cap(q.order_by(RealEstateUnit.id.desc()))
    return jsonify(envelope if envelope else items)


@api_bp.route("/units", methods=["POST"])
@require_api("realestate", "create")
def create_unit():
    from models import UnitPriceHistory
    data = request.get_json() or {}
    unit = RealEstateUnit(
        unit_code=data.get("unit_code"),
        project_id=data.get("project_id"),
        building_id=data.get("building_id"),
        floor_id=data.get("floor_id"),
        unit_type_id=data.get("unit_type_id"),
        owner_id=data.get("owner_id"),
        unit_type=data.get("unit_type"),
        area=data.get("area", 0),
        floor=data.get("floor"),
        price=data.get("price", 0),
        status=data.get("status", "available"),
    )
    db.session.add(unit)
    db.session.flush()
    price = float(unit.price or 0)
    if price > 0:
        db.session.add(UnitPriceHistory(
            unit_id=unit.id, old_price=0, new_price=price,
            change_date=datetime.now().date(), reason=data.get("price_reason") or "السعر الابتدائي",
        ))
    db.session.commit()
    _log("create", "unit", unit.id, unit.unit_code)
    return jsonify(unit.to_dict()), 201


@api_bp.route("/units/<int:unit_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_unit(unit_id):
    from models import UnitPriceHistory
    unit = RealEstateUnit.query.get_or_404(unit_id)
    data = request.get_json() or {}
    for field in ["unit_code", "project_id", "building_id", "floor_id", "unit_type_id",
                  "owner_id", "unit_type", "area", "floor", "price", "status"]:
        if field in data:
            setattr(unit, field, data[field])
    prev_price = data.get("_prev_price")
    if prev_price is not None and float(prev_price) != float(unit.price or 0):
        db.session.add(UnitPriceHistory(
            unit_id=unit.id, old_price=float(prev_price), new_price=float(unit.price or 0),
            change_date=datetime.now().date(),
            reason=data.get("price_reason") or "تعديل السعر",
        ))
    db.session.commit()
    _log("update", "unit", unit.id, unit.unit_code)
    return jsonify(unit.to_dict())


@api_bp.route("/units/<int:unit_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_unit(unit_id):
    unit = RealEstateUnit.query.get_or_404(unit_id)
    code = unit.unit_code
    db.session.delete(unit)
    db.session.commit()
    _log("delete", "unit", unit_id, code)
    return jsonify({"success": True})


# ============ الموظفين ============

@api_bp.route("/employees", methods=["GET"])
@require_api_any("view", ["hr", "crm", "sales"])
def list_employees():
    q = Employee.query
    search = request.args.get("search", "").strip()
    if search:
        q = q.filter(Employee.full_name.ilike("%" + search + "%"))
    items, envelope = paged_or_cap(q.order_by(Employee.created_at.desc()))
    return jsonify(envelope if envelope else items)


@api_bp.route("/employees", methods=["POST"])
@require_api("hr", "create")
def create_employee():
    data = request.get_json() or {}
    employee = Employee(
        full_name=data.get("full_name"),
        national_id=data.get("national_id"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        department=data.get("department"),
        position=data.get("position"),
        salary=data.get("salary", 0),
        status=data.get("status", "active"),
    )
    db.session.add(employee)
    db.session.commit()
    _log("create", "employee", employee.id, employee.full_name)
    return jsonify(employee.to_dict()), 201


@api_bp.route("/employees/<int:employee_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    data = request.get_json() or {}
    for field in ["full_name", "national_id", "phone", "email", "address",
                  "department", "position", "salary", "status"]:
        if field in data:
            setattr(employee, field, data[field])
    db.session.commit()
    _log("update", "employee", employee.id, employee.full_name)
    return jsonify(employee.to_dict())


@api_bp.route("/employees/<int:employee_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    name = employee.full_name
    db.session.delete(employee)
    db.session.commit()
    _log("delete", "employee", employee_id, name)
    return jsonify({"success": True})


# ============ العملاء ============

@api_bp.route("/customers", methods=["GET"])
@require_api_any("view", ["sales", "crm"])
def list_customers():
    q = Customer.query
    search = request.args.get("search", "").strip()
    if search:
        q = q.filter(Customer.full_name.ilike("%" + search + "%"))
    items, envelope = paged_or_cap(q.order_by(Customer.created_at.desc()))
    return jsonify(envelope if envelope else items)


@api_bp.route("/customers", methods=["POST"])
@require_api_any("create", ["sales", "crm"])
def create_customer():
    data = request.get_json() or {}
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
    _log("create", "customer", customer.id, customer.full_name)
    return jsonify(customer.to_dict()), 201


@api_bp.route("/customers/<int:customer_id>", methods=["PUT"])
@require_api_any("edit", ["sales", "crm"])
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.get_json() or {}
    for field in ["full_name", "phone", "email", "address", "type", "company", "notes", "is_active"]:
        if field in data:
            setattr(customer, field, data[field])
    db.session.commit()
    _log("update", "customer", customer.id, customer.full_name)
    return jsonify(customer.to_dict())


@api_bp.route("/customers/<int:customer_id>", methods=["DELETE"])
@require_api_any("delete", ["sales", "crm"])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    name = customer.full_name
    try:
        db.session.delete(customer)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "customer_has_related"}), 400
    _log("delete", "customer", customer_id, name)
    return jsonify({"success": True})


# ============ الموردين ============

@api_bp.route("/suppliers", methods=["GET"])
@require_api("procurement", "view")
def list_suppliers():
    q = Supplier.query
    search = request.args.get("search", "").strip()
    if search:
        q = q.filter(Supplier.company_name.ilike("%" + search + "%"))
    items, envelope = paged_or_cap(q.order_by(Supplier.created_at.desc()))
    return jsonify(envelope if envelope else items)


@api_bp.route("/suppliers", methods=["POST"])
@require_api("procurement", "create")
def create_supplier():
    data = request.get_json() or {}
    supplier = Supplier(
        company_name=data.get("company_name"),
        contact_name=data.get("contact_name"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
        category=data.get("category"),
    )
    db.session.add(supplier)
    db.session.commit()
    _log("create", "supplier", supplier.id, supplier.company_name)
    return jsonify(supplier.to_dict()), 201


@api_bp.route("/suppliers/<int:supplier_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json() or {}
    for field in ["company_name", "contact_name", "phone", "email", "address", "category"]:
        if field in data:
            setattr(supplier, field, data[field])
    db.session.commit()
    _log("update", "supplier", supplier.id, supplier.company_name)
    return jsonify(supplier.to_dict())


@api_bp.route("/suppliers/<int:supplier_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    name = supplier.company_name
    db.session.delete(supplier)
    db.session.commit()
    _log("delete", "supplier", supplier_id, name)
    return jsonify({"success": True})


# ============ الفواتير ============

@api_bp.route("/invoices", methods=["GET"])
@require_api("finance", "view")
def list_invoices():
    q = Invoice.query
    fy_id = request.args.get("financial_year_id", type=int)
    invoice_type = request.args.get("type")
    status = request.args.get("status")
    if fy_id:
        q = q.filter_by(financial_year_id=fy_id)
    if invoice_type:
        q = q.filter_by(invoice_type=invoice_type)
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q.order_by(Invoice.created_at.desc()))
    return jsonify(envelope if envelope else items)


def _build_invoice_items(invoice, items_data):
    invoice.items = []
    for it in items_data:
        if not isinstance(it, dict):
            continue
        description = it.get("description") or ""
        if not description.strip():
            continue
        invoice.items.append(InvoiceItem(
            item_id=it.get("item_id"),
            warehouse_id=it.get("warehouse_id"),
            description=description,
            quantity=float(it.get("quantity", 1) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
            expiry_date=parse_date(it.get("expiry_date")),
        ))


@api_bp.route("/invoices", methods=["POST"])
@require_api("finance", "create")
def create_invoice():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    invoice = Invoice(
        invoice_number=data.get("invoice_number"),
        invoice_type=data.get("invoice_type", "sales"),
        customer_id=data.get("customer_id"),
        supplier_id=data.get("supplier_id"),
        project_id=data.get("project_id"),
        financial_year_id=fy_id,
        amount=data.get("amount", 0),
        paid_amount=data.get("paid_amount", 0),
        status=data.get("status", "pending"),
        description=data.get("description"),
        issue_date=parse_date(data.get("issue_date")),
        due_date=parse_date(data.get("due_date")),
    )
    if data.get("items"):
        _build_invoice_items(invoice, data["items"])
        computed = invoice.items_total()
        if computed is not None:
            invoice.amount = round(computed, 2)
    db.session.add(invoice)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    submit_document_for_approval("invoice", invoice.id)
    if invoice.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_invoice_entries(invoice)
            if float(invoice.paid_amount or 0) > 0:
                acct.post_payment_entries(
                    "payment", "invoice", invoice.id, invoice.paid_amount,
                    date=invoice.issue_date,
                    financial_year_id=invoice.financial_year_id,
                    is_receipt=invoice.invoice_type == "sales",
                    description=invoice.invoice_number)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    from utils.stock import apply_purchase_invoice
    apply_purchase_invoice(invoice)
    _log("create", "invoice", invoice.id, invoice.invoice_number)
    return jsonify(invoice.to_dict()), 201


@api_bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
@require_api("finance", "edit")
def update_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    data = request.get_json() or {}
    new_fy = data.get("financial_year_id")
    err = _guard_financial_year(invoice.financial_year_id, new_fy)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    from utils.stock import reverse_purchase_invoice
    reverse_purchase_invoice(invoice)
    if "financial_year_id" in data:
        invoice.financial_year_id = new_fy if new_fy not in (None, "", 0) else None
    for field in ["invoice_number", "invoice_type", "customer_id", "supplier_id",
                  "project_id", "paid_amount", "status", "description"]:
        if field in data:
            setattr(invoice, field, data[field])
    if "amount" in data and "items" not in data:
        invoice.amount = data["amount"]
    if "issue_date" in data:
        invoice.issue_date = parse_date(data["issue_date"])
    if "due_date" in data:
        invoice.due_date = parse_date(data["due_date"])
    if "items" in data:
        _build_invoice_items(invoice, data["items"])
        computed = invoice.items_total()
        if computed is not None:
            invoice.amount = round(computed, 2)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    if invoice.approval_status == "rejected":
        submit_document_for_approval("invoice", invoice.id)
    if invoice.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_invoice_entries(invoice)
            if "paid_amount" in data:
                acct.post_payment_entries(
                    "payment", "invoice", invoice.id, invoice.paid_amount,
                    date=invoice.issue_date,
                    financial_year_id=invoice.financial_year_id,
                    is_receipt=invoice.invoice_type == "sales",
                    description=invoice.invoice_number)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    from utils.stock import apply_purchase_invoice
    apply_purchase_invoice(invoice)
    _log("update", "invoice", invoice.id, invoice.invoice_number)
    return jsonify(invoice.to_dict())


@api_bp.route("/invoices/<int:invoice_id>", methods=["DELETE"])
@require_api("finance", "delete")
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    err = _guard_closed_year(invoice.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    num = invoice.invoice_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("invoice", invoice_id)
    from utils import accounting as acct
    acct.delete_source_entries("invoice", "invoice", invoice_id)
    acct.delete_source_entries("payment", "invoice", invoice_id)
    from utils.stock import reverse_purchase_invoice
    reverse_purchase_invoice(invoice)
    db.session.delete(invoice)
    db.session.commit()
    _log("delete", "invoice", invoice_id, num)
    return jsonify({"success": True})


# ============ أوامر الشراء ============

@api_bp.route("/purchase-orders", methods=["GET"])
@require_api("procurement", "view")
def list_purchase_orders():
    q = PurchaseOrder.query
    fy_id = request.args.get("financial_year_id", type=int)
    status = request.args.get("status")
    if fy_id:
        q = q.filter_by(financial_year_id=fy_id)
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q.order_by(PurchaseOrder.created_at.desc()))
    return jsonify(envelope if envelope else items)


def _build_po_items(purchase_order, items_data):
    purchase_order.items = []
    for it in items_data:
        if not isinstance(it, dict):
            continue
        description = it.get("description") or ""
        if not description.strip():
            continue
        purchase_order.items.append(PurchaseOrderItem(
            description=description,
            quantity=float(it.get("quantity", 1) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
        ))


@api_bp.route("/purchase-orders", methods=["POST"])
@require_api("procurement", "create")
def create_purchase_order():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    po = PurchaseOrder(
        po_number=data.get("po_number"),
        supplier_id=data.get("supplier_id"),
        project_id=data.get("project_id"),
        financial_year_id=fy_id,
        items_description=data.get("items_description"),
        total=data.get("total", 0),
        status=data.get("status", "pending"),
        order_date=parse_date(data.get("order_date")),
        delivery_date=parse_date(data.get("delivery_date")),
    )
    if data.get("items"):
        _build_po_items(po, data["items"])
        computed = po.items_total()
        if computed is not None:
            po.total = round(computed, 2)
    db.session.add(po)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    submit_document_for_approval("po", po.id)
    if po.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_purchase_order_entries(po)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    _log("create", "order", po.id, po.po_number)
    return jsonify(po.to_dict()), 201


@api_bp.route("/purchase-orders/<int:po_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    data = request.get_json() or {}
    new_fy = data.get("financial_year_id")
    err = _guard_financial_year(po.financial_year_id, new_fy)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if "financial_year_id" in data:
        po.financial_year_id = new_fy if new_fy not in (None, "", 0) else None
    for field in ["po_number", "supplier_id", "project_id", "items_description",
                  "status"]:
        if field in data:
            setattr(po, field, data[field])
    if "total" in data and "items" not in data:
        po.total = data["total"]
    if "order_date" in data:
        po.order_date = parse_date(data["order_date"])
    if "delivery_date" in data:
        po.delivery_date = parse_date(data["delivery_date"])
    if "items" in data:
        _build_po_items(po, data["items"])
        computed = po.items_total()
        if computed is not None:
            po.total = round(computed, 2)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    if po.approval_status == "rejected":
        submit_document_for_approval("po", po.id)
    if po.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_purchase_order_entries(po)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    _log("update", "order", po.id, po.po_number)
    return jsonify(po.to_dict())


@api_bp.route("/purchase-orders/<int:po_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    err = _guard_closed_year(po.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    num = po.po_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("po", po_id)
    from utils import accounting as acct
    acct.delete_source_entries("po", "po", po_id)
    db.session.delete(po)
    db.session.commit()
    _log("delete", "order", po_id, num)
    return jsonify({"success": True})


# ============ عقود الإيجار ============

@api_bp.route("/rental-contracts", methods=["GET"])
@require_api("rentals", "view")
def list_rental_contracts():
    q = RentalContract.query
    fy_id = request.args.get("financial_year_id", type=int)
    status = request.args.get("status")
    if fy_id:
        q = q.filter_by(financial_year_id=fy_id)
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q.order_by(RentalContract.created_at.desc()))
    return jsonify(envelope if envelope else items)


@api_bp.route("/rental-contracts", methods=["POST"])
@require_api("rentals", "create")
def create_rental_contract():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400

    # توليد رقم العقد تلقائياً إن لم يُرسل (إصلاح NotNullViolation)
    def _gen_rental_number():
        year = datetime.now().year
        prefix = f"RC-{year}-"
        last = (RentalContract.query
                .filter(RentalContract.contract_number.like(prefix + "%"))
                .order_by(RentalContract.id.desc())
                .first())
        seq = 1
        if last and last.contract_number:
            try:
                seq = int(last.contract_number.rsplit("-", 1)[-1]) + 1
            except (ValueError, IndexError):
                seq = RentalContract.query.count() + 1
        return f"{prefix}{seq:04d}"

    contract = RentalContract(
        contract_number=data.get("contract_number") or _gen_rental_number(),
        unit_id=data.get("unit_id"),
        customer_id=data.get("customer_id"),
        financial_year_id=fy_id,
        monthly_rent=data.get("monthly_rent", 0),
        status=data.get("status", "active"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
    )
    db.session.add(contract)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    submit_document_for_approval("rental_contract", contract.id)
    if contract.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_contract_entries(contract)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    _log("create", "rental", contract.id, contract.contract_number)

    # تحديث حالة الوحدة إلى مؤجرة
    unit = db.session.get(RealEstateUnit, data.get("unit_id"))
    if unit:
        unit.status = "rented"
        db.session.commit()

    return jsonify(contract.to_dict()), 201


@api_bp.route("/rental-contracts/<int:contract_id>", methods=["PUT"])
@require_api("rentals", "edit")
def update_rental_contract(contract_id):
    contract = RentalContract.query.get_or_404(contract_id)
    data = request.get_json() or {}
    new_fy = data.get("financial_year_id")
    err = _guard_financial_year(contract.financial_year_id, new_fy)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if "financial_year_id" in data:
        contract.financial_year_id = new_fy if new_fy not in (None, "", 0) else None
    for field in ["contract_number", "unit_id", "customer_id", "monthly_rent", "status"]:
        if field in data:
            setattr(contract, field, data[field])
    if "start_date" in data:
        contract.start_date = parse_date(data["start_date"])
    if "end_date" in data:
        contract.end_date = parse_date(data["end_date"])
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    if contract.approval_status == "rejected":
        submit_document_for_approval("rental_contract", contract.id)
    if contract.approval_status == "not_required":
        from utils import accounting as acct
        try:
            acct.post_contract_entries(contract)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    _log("update", "rental", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@api_bp.route("/rental-contracts/<int:contract_id>", methods=["DELETE"])
@require_api("rentals", "delete")
def delete_rental_contract(contract_id):
    contract = RentalContract.query.get_or_404(contract_id)
    err = _guard_closed_year(contract.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    num = contract.contract_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("rental_contract", contract_id)
    from utils import accounting as acct
    acct.delete_source_entries("contract", "rental_contract", contract_id)
    db.session.delete(contract)
    db.session.commit()
    _log("delete", "rental", contract_id, num)
    return jsonify({"success": True})


# ============ البحث الشامل ============

@api_bp.route("/search")
@require_any_view
def global_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    results = []

    for c in Customer.query.filter(db.or_(
        Customer.full_name.ilike(like),
        Customer.phone.ilike(like),
        Customer.email.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "customers", "id": c.id, "text": c.full_name,
            "subtext": c.phone or c.email or "", "href": "/sales",
        })

    for s in Supplier.query.filter(db.or_(
        Supplier.company_name.ilike(like),
        Supplier.contact_name.ilike(like),
        Supplier.phone.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "suppliers", "id": s.id, "text": s.company_name,
            "subtext": s.contact_name or s.phone or "", "href": "/procurement",
        })

    for p in Project.query.filter(db.or_(
        Project.name.ilike(like),
        Project.location.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "projects", "id": p.id, "text": p.name,
            "subtext": p.location or "", "href": "/projects",
        })

    for u in RealEstateUnit.query.filter(RealEstateUnit.unit_code.ilike(like)).limit(8).all():
        results.append({
            "group": "units", "id": u.id, "text": u.unit_code,
            "subtext": u.unit_type or "", "href": "/real-estate",
        })

    for i in Invoice.query.filter(db.or_(
        Invoice.invoice_number.ilike(like),
        Invoice.description.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "invoices", "id": i.id, "text": i.invoice_number,
            "subtext": i.description or "", "href": "/finance",
        })

    for e in Employee.query.filter(db.or_(
        Employee.full_name.ilike(like),
        Employee.position.ilike(like),
        Employee.email.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "employees", "id": e.id, "text": e.full_name,
            "subtext": e.position or e.department or "", "href": "/hr",
        })

    for r in RentalContract.query.filter(RentalContract.contract_number.ilike(like)).limit(8).all():
        results.append({
            "group": "rentals", "id": r.id, "text": r.contract_number,
            "subtext": "", "href": "/rentals",
        })

    for so in SalesOrder.query.filter(SalesOrder.order_number.ilike(like)).limit(8).all():
        results.append({
            "group": "sales_orders", "id": so.id, "text": so.order_number,
            "subtext": so.customer.full_name if so.customer else "",
            "href": f"/sales?q={so.id}",
        })

    for sr in SalesReturn.query.filter(db.or_(
        SalesReturn.return_number.ilike(like),
        SalesReturn.reason.ilike(like),
    )).limit(8).all():
        results.append({
            "group": "sales_returns", "id": sr.id, "text": sr.return_number,
            "subtext": sr.reason or "",
            "href": f"/sales?q={sr.id}",
        })

    return jsonify(results)


# ============ الإشعارات ============

NOTIF_MSGS = {
    "ar": {
        "overdue": "فواتير متأخرة",
        "overdue_msg": "فاتورة {num} متأخرة {days} يوم، الرصيد {amount}",
        "expiring": "عقود تنتهي قريباً",
        "expiring_msg": "عقد {num} ينتهي في {date}",
        "vacant": "وحدات شاغرة",
        "vacant_msg": "الوحدة {code} شاغرة",
        "overdue_inst": "أقساط متأخرة",
        "overdue_inst_msg": "القسط رقم {num} للخطة #{plan} متأخر {days} يوم، المتبقي {amount}",
        "pending_approval": "موافقات معلقة",
        "pending_approval_msg": "يوجد {count} مستند بانتظار موافقتك",
    },
    "en": {
        "overdue": "Overdue invoices",
        "overdue_msg": "Invoice {num} is {days} day(s) overdue, balance {amount}",
        "expiring": "Contracts expiring soon",
        "expiring_msg": "Contract {num} ends on {date}",
        "vacant": "Vacant units",
        "vacant_msg": "Unit {code} is vacant",
        "overdue_inst": "Overdue installments",
        "overdue_inst_msg": "Installment #{num} of plan #{plan} is {days} day(s) overdue, balance {amount}",
        "pending_approval": "Pending approvals",
        "pending_approval_msg": "{count} document(s) await your approval",
    },
}


@api_bp.route("/notifications")
@require_any_view
def notifications():
    today = datetime.now().date()
    lang = request.args.get("lang") if request.args.get("lang") in NOTIF_MSGS else "ar"
    L = NOTIF_MSGS[lang]
    notifs = []

    for inv in Invoice.query.filter(
        Invoice.status.in_(["pending", "partial", "overdue"]),
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
    ).limit(10).all():
        days = (today - inv.due_date).days
        balance = float((inv.amount or 0) - (inv.paid_amount or 0))
        notifs.append({
            "type": "overdue_invoice",
            "severity": "high",
            "href": "/finance",
            "title": L["overdue"],
            "message": L["overdue_msg"].format(
                num=inv.invoice_number, days=days, amount="%.2f" % balance),
        })

    end_soon = today + timedelta(days=30)
    for rc in RentalContract.query.filter(
        RentalContract.status == "active",
        RentalContract.end_date.isnot(None),
        RentalContract.end_date >= today,
        RentalContract.end_date <= end_soon,
    ).limit(10).all():
        notifs.append({
            "type": "expiring_contract",
            "severity": "medium",
            "href": "/rentals",
            "title": L["expiring"],
            "message": L["expiring_msg"].format(
                num=rc.contract_number, date=rc.end_date.isoformat()),
        })

    for u in RealEstateUnit.query.filter_by(status="available").limit(10).all():
        project = u.project.name if u.project else ""
        notifs.append({
            "type": "vacant_unit",
            "severity": "low",
            "href": "/real-estate",
            "title": L["vacant"],
            "message": L["vacant_msg"].format(code=u.unit_code, project=project),
        })

    for inst in Installment.query.filter(
        Installment.status.in_(["pending", "partial", "overdue"]),
        Installment.due_date.isnot(None),
        Installment.due_date < today,
    ).limit(10).all():
        plan = db.session.get(PaymentPlan, inst.plan_id)
        if not plan:
            continue
        days = (today - inst.due_date).days
        balance = float(inst.amount or 0) - float(inst.paid_amount or 0)
        notifs.append({
            "type": "overdue_installment",
            "severity": "high",
            "href": "/real-estate",
            "title": L["overdue_inst"],
            "message": L["overdue_inst_msg"].format(
                num=inst.installment_number, plan=plan.id, days=days, amount="%.2f" % balance),
        })

    from models import ApprovalRequest
    from utils.workflow import user_is_approver
    my_role = session.get("role", "")
    pending_reqs = [r for r in ApprovalRequest.query.filter_by(
        status="pending").all() if user_is_approver(r)]
    if pending_reqs:
        notifs.append({
            "type": "pending_approval",
            "severity": "medium",
            "href": "/workflow/approvals",
            "title": L["pending_approval"],
            "message": L["pending_approval_msg"].format(count=len(pending_reqs)),
        })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    notifs.sort(key=lambda n: severity_order[n["severity"]])
    return jsonify(notifs)


# ============ خطط الأقساط ============

def _installment_status(inst, today=None):
    today = today or datetime.now().date()
    balance = float(inst.amount or 0) - float(inst.paid_amount or 0)
    if balance <= 0:
        return "paid"
    if float(inst.paid_amount or 0) > 0:
        return "partial"
    if inst.due_date and inst.due_date < today:
        return "overdue"
    return "pending"


def _plan_status(plan):
    today = datetime.now().date()
    if not plan.installments:
        return "active"
    for inst in plan.installments:
        if _installment_status(inst, today) in ("overdue",):
            return "overdue"
    if all(_installment_status(i, today) == "paid" for i in plan.installments):
        return "completed"
    return "active"


@api_bp.route("/payment-plans", methods=["GET"])
@require_api("realestate", "view")
def list_payment_plans():
    q = PaymentPlan.query
    fy_id = request.args.get("financial_year_id", type=int)
    if fy_id:
        q = q.filter_by(financial_year_id=fy_id)

    def _plan_dict(p):
        # حساب الحالة ديناميكياً دون تعديل قاعدة البيانات في طلب GET
        p.status = _plan_status(p)
        for i in p.installments:
            i.status = _installment_status(i)
        return p.to_dict()

    items, envelope = paged_or_cap(q.order_by(PaymentPlan.id.desc()), serializer=_plan_dict)
    return jsonify(envelope if envelope else items)


@api_bp.route("/payment-plans", methods=["POST"])
@require_api("realestate", "create")
def create_payment_plan():
    data = request.get_json(silent=True) or {}
    unit_id = data.get("unit_id")
    customer_id = data.get("customer_id")
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    total = float(data.get("total_amount") or 0)
    down = float(data.get("down_payment") or 0)
    months = int(data.get("months") or 1)
    start = parse_date(data.get("start_date"))
    monthly = float(data.get("monthly_amount") or 0)

    if not unit_id or months <= 0:
        return jsonify({"error": "invalid_plan"}), 400

    unit = RealEstateUnit.query.get_or_404(unit_id)
    if not total:
        total = float(unit.price or 0)
    if not monthly and total > down:
        monthly = round((total - down) / months, 2)

    plan = PaymentPlan(
        unit_id=unit_id,
        customer_id=customer_id or None,
        financial_year_id=fy_id,
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
        total = d.month - 1 + n
        year = d.year + total // 12
        month = total % 12 + 1
        day = min(d.day, 28)
        return d.replace(year=year, month=month, day=day)

    start = start or datetime.now().date()
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

    if unit.status != "sold":
        unit.status = "sold"
    db.session.commit()
    _log("create", "plan", plan.id, f"unit={unit_id}")
    return jsonify(plan.to_dict()), 201


@api_bp.route("/payment-plans/aging", methods=["GET"])
@require_api("realestate", "view")
def installments_aging():
    """تقرير متأخرات الأقساط (Aging) — أرصدة غير المسدد مجمعة بأشرطة التأخر.

    bars: 0-30 / 31-60 / 61-90 / 90+ يوم تأخر عن الاستحقاق.
    """
    today = datetime.now().date()

    def _bar(days_late):
        if days_late <= 30:
            return "0-30"
        if days_late <= 60:
            return "31-60"
        if days_late <= 90:
            return "61-90"
        return "90+"

    rows = []
    overdue_insts = (Installment.query
                     .filter(Installment.due_date.isnot(None),
                             Installment.due_date < today,
                             Installment.status.in_(["pending", "partial", "overdue"]))
                     .all())
    for inst in overdue_insts:
        balance = float((inst.amount or 0) - (inst.paid_amount or 0))
        if balance <= 0:
            continue
        days_late = (today - inst.due_date).days
        plan = db.session.get(PaymentPlan, inst.plan_id)
        unit_code = plan.unit.unit_code if plan and plan.unit else None
        customer_name = (plan.customer.full_name if plan and plan.customer else None)
        rows.append({
            "installment_id": inst.id,
            "plan_id": inst.plan_id,
            "unit_code": unit_code,
            "customer_name": customer_name,
            "due_date": inst.due_date.isoformat(),
            "days_late": days_late,
            "bar": _bar(days_late),
            "balance": round(balance, 2),
        })
    rows.sort(key=lambda r: r["days_late"], reverse=True)

    buckets = ["0-30", "31-60", "61-90", "90+"]
    summary = {b: {"count": 0, "total": 0.0} for b in buckets}
    for r in rows:
        summary[r["bar"]]["count"] += 1
        summary[r["bar"]]["total"] = round(summary[r["bar"]]["total"] + r["balance"], 2)
    total_due = round(sum(r["balance"] for r in rows), 2)

    # قوائم المتأخرات القادمة خلال 30 يوماً (تنبيه استباقي)
    upcoming = (Installment.query
                .filter(Installment.due_date.isnot(None),
                        Installment.due_date >= today,
                        Installment.due_date <= today + timedelta(days=30),
                        Installment.status.in_(["pending", "partial"]))
                .count())

    return jsonify({
        "as_of": today.isoformat(),
        "rows": rows,
        "summary": summary,
        "total_overdue": total_due,
        "overdue_count": len(rows),
        "due_within_30d_count": upcoming,
    })


@api_bp.route("/payment-plans/<int:plan_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_payment_plan(plan_id):
    plan = PaymentPlan.query.get_or_404(plan_id)
    err = _guard_closed_year(plan.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    data = request.get_json(silent=True) or {}

    # تعديل العميل مسموح دائماً
    customer_id = data.get("customer_id")
    if customer_id not in (None, ""):
        plan.customer_id = customer_id or None

    # بعد تسجيل أي دفعات يُمنع تعديل بنية الخطة (مبلغ/شهور/وحدة/سنة/تاريخ)
    has_payments = any(float(i.paid_amount or 0) > 0 for i in plan.installments)
    if has_payments:
        db.session.commit()
        _log("update", "plan", plan_id, "تعديل العميل فقط (توجد دفعات)")
        return jsonify(plan.to_dict())

    unit_id = data.get("unit_id")
    if unit_id in (None, ""):
        return jsonify({"error": "invalid_plan"}), 400
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400

    new_unit = RealEstateUnit.query.get_or_404(unit_id)
    old_unit = db.session.get(RealEstateUnit, plan.unit_id)
    if fy_id is not None:
        plan.financial_year_id = fy_id
    plan.unit_id = new_unit.id
    if new_unit.status != "sold":
        new_unit.status = "sold"
    if old_unit and old_unit.id != new_unit.id and not old_unit.payment_plans:
        old_unit.status = "available"

    total = float(data.get("total_amount") or 0)
    if not total:
        total = float(plan.total_amount or 0)
    if not total:
        total = float(new_unit.price or 0)
    if "down_payment" in data:
        down = float(data.get("down_payment") or 0)
    else:
        down = float(plan.down_payment or 0)
    months = int(data.get("months") or 0)
    if not months:
        months = int(plan.months or 1)
    if months <= 0:
        return jsonify({"error": "invalid_plan"}), 400
    start = parse_date(data.get("start_date")) or plan.start_date or datetime.now().date()
    if "monthly_amount" in data:
        monthly = float(data.get("monthly_amount") or 0)
    else:
        monthly = float(plan.monthly_amount or 0)
    if not monthly and total > down:
        monthly = round((total - down) / months, 2)

    plan.total_amount = total
    plan.down_payment = down
    plan.months = months
    plan.monthly_amount = monthly
    plan.start_date = start
    plan.status = "active"

    # إعادة بناء جدول الأقساط
    for inst in list(plan.installments):
        db.session.delete(inst)
    db.session.flush()

    def add_months(d, n):
        t = d.month - 1 + n
        year = d.year + t // 12
        month = t % 12 + 1
        day = min(d.day, 28)
        return d.replace(year=year, month=month, day=day)

    start = start or datetime.now().date()
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

    db.session.commit()
    _log("update", "plan", plan_id, f"unit={unit_id} months={months}")
    plan.status = _plan_status(plan)
    return jsonify(plan.to_dict())


@api_bp.route("/payment-plans/<int:plan_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_payment_plan(plan_id):
    plan = PaymentPlan.query.get_or_404(plan_id)
    err = _guard_closed_year(plan.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    from utils import accounting as acct
    for inst in plan.installments:
        acct.delete_source_entries("installment", "installment", inst.id)
    db.session.delete(plan)
    db.session.commit()
    _log("delete", "plan", plan_id, f"plan={plan_id}")
    return jsonify({"success": True})


@api_bp.route("/installments/<int:installment_id>", methods=["PUT"])
@require_api("realestate", "edit")
def pay_installment(installment_id):
    data = request.get_json(silent=True) or {}
    inst = Installment.query.get_or_404(installment_id)
    amount = float(data.get("paid_amount") or 0)
    if amount < 0:
        return jsonify({"error": "invalid_amount"}), 400
    inst.paid_amount = amount
    inst.paid_date = parse_date(data.get("paid_date")) or datetime.now().date()
    inst.status = _installment_status(inst)
    plan = db.session.get(PaymentPlan, inst.plan_id)
    if plan:
        plan.status = _plan_status(plan)
    db.session.commit()
    from utils import accounting as acct
    if amount > 0:
        try:
            # حذف قيد الدفعة السابقة لمنع الترحيل المكرر عند تعديل السداد
            acct.delete_source_entries("installment", "installment", inst.id)
            acct.post_payment_entries(
                "installment", "installment", inst.id, amount,
                date=inst.paid_date,
                financial_year_id=plan.financial_year_id if plan else None,
                is_receipt=True,
                description=f"قسط {inst.installment_number}")
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 500
    else:
        acct.delete_source_entries("installment", "installment", inst.id)
    _log("payment", "installment", inst.id, f"inst={inst.id} plan={inst.plan_id} amount={amount}")
    return jsonify(inst.to_dict())


# ── AI Query Engine ────────────────────────────────────────────
@api_bp.route("/ai/query", methods=["POST"])
@require_any_view
def ai_query():
    # Rate limit: 5 requests per minute per IP
    limiter = current_app.config.get("RATELIMITER")
    if limiter:
        try:
            limiter.limit("5 per minute", key_func=lambda: request.remote_addr)(lambda: None)()
        except Exception:
            from utils.errlog import log_exc
            log_exc("api.ai-query-ratelimit")
    """Accept a natural-language question, run via Gemini, execute the result."""
    from ai_engine import ask_ai
    from sqlalchemy import text

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "message": "يرجى كتابة سؤال"}), 400

    result = ask_ai(question)
    if not result.get("success"):
        return jsonify(result)

    plan = result.get("data", {})
    action = plan.get("action", "CLARIFY")

    if action == "CLARIFY":
        return jsonify({"success": True, "type": "clarify",
                        "answer": plan.get("answer_hint", "يرجى توضيح السؤال")})

    if action == "TEXT":
        return jsonify({"success": True, "type": "text",
                        "answer": plan.get("answer", "")})

    # Execute query actions
    try:
        params = plan.get("params", {})
        answer_hint = plan.get("answer_hint", "")

        if action == "SQL_QUERY":
            import re as _re
            sql = params.get("sql", "")
            stripped = sql.strip()
            if not stripped.upper().startswith("SELECT"):
                return jsonify({"success": False, "message": "غير مسموح إلا بـ SELECT"})
            # قائمة بيضاء للجداول المسموحة — تمنع الوصول لجداول حساسة مثل users
            _SQL_ALLOW = {
                "employees", "customers", "suppliers", "projects", "invoices",
                "invoice_items", "purchase_orders", "rental_contracts", "rental_payments",
                "rental_renewals", "real_estate_units", "real_estate_buildings",
                "real_estate_floors", "unit_types", "real_estate_owners",
                "unit_reservations", "unit_allocations", "sales_contracts",
                "commissions", "unit_deliveries", "maintenance_requests", "unit_shares",
                "items", "item_stocks", "warehouses", "accounts", "journal_entries",
                "journal_entry_lines", "installments", "payment_plans", "hr_departments",
                "hr_positions", "hr_attendance", "hr_leaves", "cost_centers",
                "fixed_assets", "project_phases", "project_wbs_items", "project_boq_items",
            }
            _SQL_BLOCKED_COLS = {"password_hash", "password", "secret"}
            _SQL_BLOCKED_KW = [";--", "/*", "*/", "@@", "pg_", "information_schema", "pg_catalog"]
            lower_sql = stripped.lower()
            # منع أعمدة/كلمات محظورة
            for col in _SQL_BLOCKED_COLS:
                if col in lower_sql:
                    return jsonify({"success": False, "message": "استعلام غير مسموح (عمود محظور)"}), 403
            for kw in _SQL_BLOCKED_KW:
                if kw in lower_sql:
                    return jsonify({"success": False, "message": "استعلام غير مسموح (نمط محظور)"}), 403
            # تحقق من الجداول المذكورة في FROM/JOIN
            tables_in_sql = set(_re.findall(r'(?:from|join)\s+"?(\w+)"?', lower_sql))
            unknown = tables_in_sql - _SQL_ALLOW
            if unknown:
                return jsonify({"success": False,
                                "message": f"جداول غير مسموحة: {', '.join(sorted(unknown))}"}), 403
            if not tables_in_sql:
                return jsonify({"success": False, "message": "الاستعلام لا يحدد جدولاً مسموحاً"}), 400
            # منع UNION / تعدد عبارات
            if _re.search(r'\bunion\b', lower_sql) or stripped.count(";") > 1:
                return jsonify({"success": False, "message": "UNION وتعدد العبارات غير مسموح"}), 403
            rows = db.session.execute(text(stripped)).fetchall()
            cols = list(rows[0].keys()) if rows else []
            data_list = [dict(zip(cols, row)) for row in rows]
            return jsonify({"success": True, "type": "sql",
                            "answer": answer_hint, "data": data_list,
                            "columns": cols})

        elif action == "COUNT":
            table = params.get("table", "")
            filters = params.get("filters", {})
            count = _ai_count(table, filters)
            return jsonify({"success": True, "type": "count",
                            "answer": answer_hint, "count": count})

        elif action == "SUM":
            table = params.get("table", "")
            column = params.get("column", "amount")
            filters = params.get("filters", {})
            total = _ai_sum(table, column, filters)
            return jsonify({"success": True, "type": "sum",
                            "answer": answer_hint, "total": float(total or 0)})

        elif action == "SEARCH":
            table = params.get("table", "")
            columns = params.get("columns", [])
            query = params.get("query", "")
            limit = params.get("limit", 10)
            data_list = _ai_search(table, columns, query, limit)
            return jsonify({"success": True, "type": "search",
                            "answer": answer_hint, "data": data_list})

        elif action == "DASHBOARD":
            stats = _ai_dashboard()
            return jsonify({"success": True, "type": "dashboard",
                            "answer": answer_hint, "data": stats})

        else:
            return jsonify({"success": True, "type": "text",
                            "answer": answer_hint or "تم الاستعلام بنجاح"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e),
                        "answer": f"خطأ في التنفيذ: {str(e)}"})


_TABLE_MAP = {
    "employees": "employees", "employee": "employees",
    "customers": "customers", "customer": "customers",
    "suppliers": "suppliers", "supplier": "suppliers",
    "projects": "projects", "project": "projects",
    "invoices": "invoices", "invoice": "invoices",
    "items": "items", "item": "items",
    "warehouses": "warehouses", "warehouse": "warehouses",
    "accounts": "accounts", "account": "accounts",
    "journal_entries": "journal_entries",
    "installments": "installments", "installment": "installments",
    "rental_contracts": "rental_contracts",
    "hr_departments": "hr_departments", "department": "hr_departments",
}


_AI_ALLOWED_TABLES = set(_TABLE_MAP.values())

def _resolve_table(name):
    """يحل اسم الجدول — يرفض أي جدول غير مسموح."""
    real = _TABLE_MAP.get(name.lower().strip())
    if real not in _AI_ALLOWED_TABLES:
        raise ValueError(f"جدول غير مسموح: {name}")
    return real


# أعمدة مسموحة لكل جدول (لمنع حقن أسماء الأعمدة)
_AI_ALLOWED_COLUMNS = {
    "employees": {"id", "full_name", "phone", "email", "department", "status", "hire_date"},
    "customers": {"id", "full_name", "phone", "email", "type", "is_active"},
    "suppliers": {"id", "company_name", "phone", "email", "category"},
    "projects": {"id", "name", "location", "status", "priority"},
    "invoices": {"id", "invoice_number", "amount", "status", "invoice_type"},
    "items": {"id", "code", "name", "sale_price"},
    "warehouses": {"id", "code", "name"},
    "accounts": {"id", "code", "name", "type"},
    "journal_entries": {"id", "entry_number", "status"},
    "installments": {"id", "amount", "status", "due_date"},
    "rental_contracts": {"id", "contract_number", "status", "monthly_rent"},
    "hr_departments": {"id", "name", "is_active"},
}


def _ai_count(table, filters):
    real = _resolve_table(table)
    allowed_cols = _AI_ALLOWED_COLUMNS.get(real, set())
    sql = f"SELECT COUNT(*) as cnt FROM {real}"
    wheres, vals = [], {}
    for k, v in filters.items():
        if k not in allowed_cols:
            raise ValueError(f"عمود غير مسموح: {k}")
        wheres.append(f"{k} = :{k}")
        vals[k] = v
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    row = db.session.execute(text(sql), vals).fetchone()
    return row[0] if row else 0


def _ai_sum(table, column, filters):
    real = _resolve_table(table)
    allowed_cols = _AI_ALLOWED_COLUMNS.get(real, set())
    if column not in allowed_cols:
        raise ValueError(f"عمود غير مسموح: {column}")
    sql = f"SELECT COALESCE(SUM({column}), 0) as total FROM {real}"
    wheres, vals = [], {}
    for k, v in filters.items():
        if k not in allowed_cols:
            raise ValueError(f"عمود غير مسموح: {k}")
        wheres.append(f"{k} = :{k}")
        vals[k] = v
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    row = db.session.execute(text(sql), vals).fetchone()
    return row[0] if row else 0


def _ai_search(table, columns, query, limit):
    real = _resolve_table(table)
    allowed_cols = _AI_ALLOWED_COLUMNS.get(real, set())
    cols = [c for c in (columns or ["id"]) if c in allowed_cols]
    if not cols:
        cols = ["id"]
    # تحديد الحد الأقصى
    try:
        limit = min(max(int(limit), 1), 50)
    except (TypeError, ValueError):
        limit = 10
    col_str = ", ".join(cols)
    conditions = " OR ".join([f"{c} ILIKE :q" for c in cols])
    sql = f"SELECT {col_str} FROM {real} WHERE {conditions} LIMIT :lim"
    rows = db.session.execute(text(sql), {"q": f"%{query}%", "lim": limit}).fetchall()
    return [dict(zip(cols, row)) for row in rows]


def _ai_dashboard():
    stats = {}
    try:
        stats["employees_active"] = _ai_count("employees", {"status": "active"})
        stats["customers_count"] = _ai_count("customers", {})
        stats["invoices_count"] = _ai_count("invoices", {})
        stats["overdue_installments"] = _ai_count("installments", {"status": "overdue"})
        row = db.session.execute(text(
            "SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE status='paid'"
        )).fetchone()
        stats["total_revenue"] = float(row[0] or 0)
        row2 = db.session.execute(text(
            "SELECT COALESCE(SUM(amount - paid_amount), 0) FROM invoices WHERE status != 'paid'"
        )).fetchone()
        stats["total_receivable"] = float(row2[0] or 0)
    except Exception:
        from utils.errlog import log_exc
        log_exc("api.dashboard-stats")
    return stats
