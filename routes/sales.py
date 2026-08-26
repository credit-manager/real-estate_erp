from flask import Blueprint, request, jsonify
from datetime import datetime, date
from database import db
from models import (
    Customer, Employee, Quote,
    Invoice, InvoiceItem,
    SalesOrder, SalesOrderItem,
    SalesReturn, SalesReturnItem,
    SalesCommission,
)
from permissions import require_api
from routes.financial_years import financial_year_error

sales_bp = Blueprint("sales_api", __name__, url_prefix="/api/sales")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_float(value, default=0):
    try:
        return float(value) if value not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _log(action, entity, entity_id, description):
    from auditlog import log_action
    log_action(action, entity, entity_id, description)


def _resolve_financial_year(data):
    fy_id = data.get("financial_year_id")
    if fy_id in (None, "", 0):
        return None, None
    err = financial_year_error(fy_id)
    if err:
        return None, err
    return fy_id, None


def _guard_financial_year(current_fy_id, new_fy_id):
    err = financial_year_error(new_fy_id)
    if err:
        return err
    if current_fy_id and financial_year_error(current_fy_id):
        return "financialYears.closed"
    return None


def _guard_closed_year(financial_year_id):
    if financial_year_id and financial_year_error(financial_year_id):
        return "financialYears.closed"
    return None


def _next_number(model, prefix, col):
    from utils.docnum import seq_by_prefix
    year = datetime.now().year
    return seq_by_prefix(model, col, f"{prefix}-{year}-")


def _build_items(cls, items_data):
    items = []
    for it in items_data or []:
        if not isinstance(it, dict):
            continue
        description = (it.get("description") or "").strip()
        if not description:
            continue
        items.append(cls(
            description=description,
            quantity=parse_float(it.get("quantity"), 1),
            unit_price=parse_float(it.get("unit_price")),
            tax_rate=parse_float(it.get("tax_rate")),
        ))
    return items


# ============ ملخص الوحدة ============

@sales_bp.route("/summary", methods=["GET"])
@require_api("sales", "view")
def summary():
    sales_invoices = Invoice.query.filter_by(invoice_type="sales").all()
    orders = SalesOrder.query.all()
    returns = SalesReturn.query.all()
    commissions = SalesCommission.query.all()
    total_revenue = sum(float(i.amount or 0) for i in sales_invoices)
    paid_revenue = sum(float(i.paid_amount or 0) for i in sales_invoices)
    pending_orders = [o for o in orders if o.status in ("draft", "confirmed", "delivered")]
    today = date.today()
    return jsonify({
        "customers_count": Customer.query.count(),
        "quotes_count": Quote.query.filter(Quote.status.in_(["draft", "sent"])).count(),
        "orders_count": len(orders),
        "orders_open": len(pending_orders),
        "orders_value": round(sum(float(o.amount or 0) for o in pending_orders), 2),
        "invoices_count": len(sales_invoices),
        "total_revenue": round(total_revenue, 2),
        "paid_revenue": round(paid_revenue, 2),
        "pending_revenue": round(total_revenue - paid_revenue, 2),
        "returns_count": len(returns),
        "returns_value": round(sum(float(r.amount or 0) for r in returns), 2),
        "commissions_total": round(sum(float(c.amount or 0) for c in commissions if c.status == "paid"), 2),
        "commissions_pending": sum(1 for c in commissions if c.status == "pending"),
        "returns_today": sum(1 for r in returns if r.return_date == today),
        "overdue_orders": sum(1 for o in orders if o.due_date and o.due_date < today and o.status in ("draft", "confirmed", "delivered")),
    })


# ============ أوامر البيع ============

@sales_bp.route("/orders", methods=["GET"])
@require_api("sales", "view")
def list_orders():
    orders = SalesOrder.query.order_by(SalesOrder.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@sales_bp.route("/orders", methods=["POST"])
@require_api("sales", "create")
def create_order():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    order = SalesOrder(
        order_number=_next_number(SalesOrder, "SO", SalesOrder.order_number),
        customer_id=data.get("customer_id") or None,
        salesperson_id=data.get("salesperson_id") or None,
        quote_id=data.get("quote_id") or None,
        financial_year_id=fy_id,
        order_date=parse_date(data.get("order_date")) or date.today(),
        due_date=parse_date(data.get("due_date")),
        status=data.get("status", "draft"),
        paid_amount=parse_float(data.get("paid_amount")),
        notes=data.get("notes"),
    )
    order.items = _build_items(SalesOrderItem, data.get("items"))
    computed = order.items_total()
    if computed is not None:
        order.amount = round(computed, 2)
    else:
        order.amount = parse_float(data.get("amount"))
    db.session.add(order)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    submit_document_for_approval("sales_order", order.id)
    _log("create", "sales_order", order.id, order.order_number)
    return jsonify(order.to_dict()), 201


@sales_bp.route("/orders/<int:order_id>", methods=["PUT"])
@require_api("sales", "edit")
def update_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    data = request.get_json() or {}
    err = _guard_financial_year(order.financial_year_id, data.get("financial_year_id"))
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    for field in ["customer_id", "salesperson_id", "quote_id", "status",
                  "paid_amount", "notes"]:
        if field in data:
            setattr(order, field, data[field])
    if "financial_year_id" in data:
        order.financial_year_id = data["financial_year_id"] or None
    if "order_date" in data:
        order.order_date = parse_date(data["order_date"])
    if "due_date" in data:
        order.due_date = parse_date(data["due_date"])
    if "items" in data:
        order.items = _build_items(SalesOrderItem, data.get("items"))
        computed = order.items_total()
        if computed is not None:
            order.amount = round(computed, 2)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    if order.approval_status == "rejected":
        submit_document_for_approval("sales_order", order.id)
    _log("update", "sales_order", order.id, order.order_number)
    return jsonify(order.to_dict())


@sales_bp.route("/orders/<int:order_id>", methods=["DELETE"])
@require_api("sales", "delete")
def delete_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    err = _guard_closed_year(order.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if order.commissions:
        return jsonify({"message": "sales.hasCommissions", "error_key": "sales.hasCommissions"}), 400
    number = order.order_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("sales_order", order_id)
    # Soft-delete: إلغاء الأمر وختم وقت الحذف — لا حذف فعلي لسجل مالي
    if hasattr(order, "deleted_at"):
        from datetime import datetime as _dt
        order.status = "cancelled"
        order.deleted_at = _dt.now()
    else:
        for item in order.items:
            db.session.delete(item)
        order.status = "cancelled"
    db.session.commit()
    _log("delete", "sales_order", order_id, number)
    return jsonify({"success": True})


@sales_bp.route("/orders/<int:order_id>/invoice", methods=["POST"])
@require_api("sales", "create")
def order_to_invoice(order_id):
    """تحويل أمر بيع → فاتورة بيع."""
    order = SalesOrder.query.get_or_404(order_id)
    if order.status == "cancelled":
        return jsonify({"message": "sales.orderCancelled", "error_key": "sales.orderCancelled"}), 400
    invoice = Invoice(
        invoice_number=_next_number(Invoice, "INV", Invoice.invoice_number),
        invoice_type="sales",
        customer_id=order.customer_id,
        financial_year_id=order.financial_year_id,
        amount=float(order.amount or 0),
        paid_amount=float(order.paid_amount or 0),
        status="pending",
        description=f"{order.order_number} - {order.notes or ''}".strip(),
        issue_date=date.today(),
    )
    invoice.items = [
        InvoiceItem(
            description=it.description,
            quantity=it.quantity,
            unit_price=it.unit_price,
            tax_rate=it.tax_rate,
        )
        for it in order.items
    ]
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
                    is_receipt=True,
                    description=invoice.invoice_number)
        except ValueError as e:
            db.session.rollback()
            # Soft-delete: mark invoice as cancelled instead of actual deletion
            invoice.status = "cancelled"
            db.session.commit()
            return jsonify({"message": str(e), "error_key": str(e)}), 400
    order.status = "completed"
    db.session.commit()
    _log("create", "invoice", invoice.id, invoice.invoice_number)
    _log("update", "sales_order", order.id, f"{order.order_number} → فاتورة")
    return jsonify(invoice.to_dict()), 201


# ============ الفواتير (مبيعات) ============

@sales_bp.route("/invoices", methods=["GET"])
@require_api("sales", "view")
def list_sales_invoices():
    invoices = Invoice.query.filter_by(invoice_type="sales").filter(Invoice.deleted_at.is_(None)).order_by(Invoice.created_at.desc()).all()
    return jsonify([i.to_dict() for i in invoices])


@sales_bp.route("/invoices", methods=["POST"])
@require_api("sales", "create")
def create_sales_invoice():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    invoice = Invoice(
        invoice_number=data.get("invoice_number") or _next_number(Invoice, "INV", Invoice.invoice_number),
        invoice_type="sales",
        customer_id=data.get("customer_id") or None,
        financial_year_id=fy_id,
        paid_amount=parse_float(data.get("paid_amount")),
        status=data.get("status", "pending"),
        description=data.get("description"),
        issue_date=parse_date(data.get("issue_date")),
        due_date=parse_date(data.get("due_date")),
    )
    invoice.items = _build_items(InvoiceItem, data.get("items"))
    computed = invoice.items_total()
    if computed is not None:
        invoice.amount = round(computed, 2)
    else:
        invoice.amount = parse_float(data.get("amount"))
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
                    is_receipt=True,
                    description=invoice.invoice_number)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
    _log("create", "invoice", invoice.id, invoice.invoice_number)
    return jsonify(invoice.to_dict()), 201


@sales_bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
@require_api("sales", "edit")
def update_sales_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.invoice_type != "sales":
        return jsonify({"message": "sales.notSalesInvoice", "error_key": "sales.notSalesInvoice"}), 400
    data = request.get_json() or {}
    err = _guard_financial_year(invoice.financial_year_id, data.get("financial_year_id"))
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    for field in ["customer_id", "paid_amount", "status", "description"]:
        if field in data:
            setattr(invoice, field, data[field])
    if "financial_year_id" in data:
        invoice.financial_year_id = data["financial_year_id"] or None
    if "issue_date" in data:
        invoice.issue_date = parse_date(data["issue_date"])
    if "due_date" in data:
        invoice.due_date = parse_date(data["due_date"])
    if "items" in data:
        invoice.items = _build_items(InvoiceItem, data.get("items"))
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
                    is_receipt=True,
                    description=invoice.invoice_number)
        except ValueError as e:
            return jsonify({"message": str(e), "error_key": str(e)}), 400
    _log("update", "invoice", invoice.id, invoice.invoice_number)
    return jsonify(invoice.to_dict())


@sales_bp.route("/invoices/<int:invoice_id>", methods=["DELETE"])
@require_api("sales", "delete")
def delete_sales_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.deleted_at:
        return jsonify({"message": "common.notFound"}), 404
    if invoice.invoice_type != "sales":
        return jsonify({"message": "sales.notSalesInvoice", "error_key": "sales.notSalesInvoice"}), 400
    err = _guard_closed_year(invoice.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if invoice.sales_returns:
        return jsonify({"message": "sales.hasReturns", "error_key": "sales.hasReturns"}), 400
    if invoice.paid_amount and float(invoice.paid_amount) > 0:
        return jsonify({"message": "sales.invoiceHasPayments", "error_key": "sales.invoiceHasPayments"}), 400
    number = invoice.invoice_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("invoice", invoice_id)
    from utils import accounting as acct
    acct.delete_source_entries("invoice", "invoice", invoice_id)
    acct.delete_source_entries("payment", "invoice", invoice_id)
    # Soft-delete: تعليم الفاتورة ملغاة + ختم وقت الحذف بدل الحذف الفعلي
    invoice.status = "cancelled"
    from datetime import datetime as _dt
    invoice.deleted_at = _dt.now()
    db.session.commit()
    _log("delete", "invoice", invoice_id, number)
    return jsonify({"success": True})


@sales_bp.route("/invoices/<int:invoice_id>/pay", methods=["POST"])
@require_api("sales", "edit")
def pay_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.invoice_type != "sales":
        return jsonify({"message": "sales.notSalesInvoice", "error_key": "sales.notSalesInvoice"}), 400
    data = request.get_json() or {}
    amount = parse_float(data.get("amount"))
    if amount <= 0:
        return jsonify({"message": "sales.payAmountRequired", "error_key": "sales.payAmountRequired"}), 400
    balance = float(invoice.amount or 0) - float(invoice.paid_amount or 0)
    amount = min(amount, balance)
    invoice.paid_amount = float(invoice.paid_amount or 0) + amount
    if float(invoice.paid_amount or 0) >= float(invoice.amount or 0):
        invoice.status = "paid"
    else:
        invoice.status = "partial"
    from utils import accounting as acct
    try:
        acct.post_payment_entries(
            "payment", "invoice", invoice.id, invoice.paid_amount,
            date=parse_date(data.get("payment_date")) or invoice.issue_date,
            financial_year_id=invoice.financial_year_id,
            is_receipt=True,
            description=invoice.invoice_number)
    except ValueError as e:
        return jsonify({"message": str(e), "error_key": str(e)}), 400
    db.session.commit()
    _log("update", "invoice", invoice.id, f"تحصيل {amount}")
    return jsonify(invoice.to_dict())


# ============ المرتجعات ============

@sales_bp.route("/returns", methods=["GET"])
@require_api("sales", "view")
def list_returns():
    returns = SalesReturn.query.order_by(SalesReturn.created_at.desc()).all()
    return jsonify([r.to_dict() for r in returns])


@sales_bp.route("/returns", methods=["POST"])
@require_api("sales", "create")
def create_return():
    data = request.get_json() or {}
    fy_id, err = _resolve_financial_year(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    ret = SalesReturn(
        return_number=_next_number(SalesReturn, "SR", SalesReturn.return_number),
        invoice_id=data.get("invoice_id") or None,
        customer_id=data.get("customer_id") or None,
        financial_year_id=fy_id,
        return_date=parse_date(data.get("return_date")) or date.today(),
        status=data.get("status", "draft"),
        reason=data.get("reason"),
    )
    ret.items = _build_items(SalesReturnItem, data.get("items"))
    computed = ret.items_total()
    if computed is not None:
        ret.amount = round(computed, 2)
    else:
        ret.amount = parse_float(data.get("amount"))
    db.session.add(ret)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    submit_document_for_approval("sales_return", ret.id)
    _log("create", "sales_return", ret.id, ret.return_number)
    return jsonify(ret.to_dict()), 201


@sales_bp.route("/returns/<int:return_id>", methods=["PUT"])
@require_api("sales", "edit")
def update_return(return_id):
    ret = SalesReturn.query.get_or_404(return_id)
    data = request.get_json() or {}
    err = _guard_financial_year(ret.financial_year_id, data.get("financial_year_id"))
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    for field in ["invoice_id", "customer_id", "status", "reason"]:
        if field in data:
            setattr(ret, field, data[field])
    if "financial_year_id" in data:
        ret.financial_year_id = data["financial_year_id"] or None
    if "return_date" in data:
        ret.return_date = parse_date(data["return_date"])
    if "items" in data:
        ret.items = _build_items(SalesReturnItem, data.get("items"))
        computed = ret.items_total()
        if computed is not None:
            ret.amount = round(computed, 2)
    db.session.commit()
    from utils.workflow import submit_document_for_approval
    if ret.approval_status == "rejected":
        submit_document_for_approval("sales_return", ret.id)
    _log("update", "sales_return", ret.id, ret.return_number)
    return jsonify(ret.to_dict())


@sales_bp.route("/returns/<int:return_id>", methods=["DELETE"])
@require_api("sales", "delete")
def delete_return(return_id):
    ret = SalesReturn.query.get_or_404(return_id)
    err = _guard_closed_year(ret.financial_year_id)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    number = ret.return_number
    from utils.workflow import cancel_document_approval
    cancel_document_approval("sales_return", return_id)
    for item in ret.items:
        db.session.delete(item)
    db.session.delete(ret)
    db.session.commit()
    _log("delete", "sales_return", return_id, number)
    return jsonify({"success": True})


# ============ العمولات ============

@sales_bp.route("/commissions", methods=["GET"])
@require_api("sales", "view")
def list_commissions():
    commissions = SalesCommission.query.order_by(SalesCommission.created_at.desc()).all()
    return jsonify([c.to_dict() for c in commissions])


@sales_bp.route("/commissions", methods=["POST"])
@require_api("sales", "create")
def create_commission():
    data = request.get_json() or {}
    amount = parse_float(data.get("amount"))
    rate = parse_float(data.get("rate"))
    if amount <= 0:
        return jsonify({"message": "sales.commissionAmountRequired", "error_key": "sales.commissionAmountRequired"}), 400
    commission = SalesCommission(
        salesperson_id=data.get("salesperson_id") or None,
        order_id=data.get("order_id") or None,
        invoice_id=data.get("invoice_id") or None,
        commission_date=parse_date(data.get("commission_date")) or date.today(),
        amount=round(amount, 2),
        rate=rate,
        status=data.get("status", "pending"),
        notes=data.get("notes"),
    )
    db.session.add(commission)
    db.session.commit()
    _log("create", "sales_commission", commission.id, f"{commission.amount} للمندوب {commission.salesperson_id}")
    return jsonify(commission.to_dict()), 201


@sales_bp.route("/commissions/<int:commission_id>", methods=["PUT"])
@require_api("sales", "edit")
def update_commission(commission_id):
    commission = SalesCommission.query.get_or_404(commission_id)
    data = request.get_json() or {}
    for field in ["salesperson_id", "order_id", "invoice_id", "amount", "rate", "status", "notes"]:
        if field in data:
            setattr(commission, field, data[field])
    if "commission_date" in data:
        commission.commission_date = parse_date(data["commission_date"])
    db.session.commit()
    _log("update", "sales_commission", commission.id, "تعديل عمولة")
    return jsonify(commission.to_dict())


@sales_bp.route("/commissions/<int:commission_id>", methods=["DELETE"])
@require_api("sales", "delete")
def delete_commission(commission_id):
    commission = SalesCommission.query.get_or_404(commission_id)
    db.session.delete(commission)
    db.session.commit()
    _log("delete", "sales_commission", commission_id, "حذف عمولة")
    return jsonify({"success": True})


@sales_bp.route("/commissions/<int:commission_id>/status", methods=["POST"])
@require_api("sales", "edit")
def commission_status(commission_id):
    commission = SalesCommission.query.get_or_404(commission_id)
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ("pending", "approved", "paid", "cancelled"):
        return jsonify({"message": "sales.invalidStatus", "error_key": "sales.invalidStatus"}), 400
    commission.status = status
    db.session.commit()
    _log("update", "sales_commission", commission.id, f"حالة العمولة: {status}")
    return jsonify(commission.to_dict())


@sales_bp.route("/commissions/auto", methods=["POST"])
@require_api("sales", "create")
def auto_commissions():
    """إنشاء عمولات تلقائياً لأوامر البيع المكتملة (نسبة من إعدادات المبيعات)."""
    import utils.settings as settings_module
    rate = settings_module.get_float("sales_commission_rate", 0)
    if rate <= 0:
        return jsonify({"message": "sales.autoRateZero", "error_key": "sales.autoRateZero"}), 400
    created = 0
    for order in SalesOrder.query.filter_by(status="completed").all():
        if not order.salesperson_id or order.commissions:
            continue
        amount = round(float(order.amount or 0) * rate / 100, 2)
        if amount <= 0:
            continue
        db.session.add(SalesCommission(
            salesperson_id=order.salesperson_id,
            order_id=order.id,
            commission_date=date.today(),
            amount=amount,
            rate=rate,
            status="pending",
        ))
        created += 1
    db.session.commit()
    _log("create", "sales_commission", 0, f"عمولات تلقائية: {created}")
    return jsonify({"success": True, "created": created})


# ============ متابعة فريق المبيعات ============

@sales_bp.route("/team", methods=["GET"])
@require_api("sales", "view")
def team():
    employees = Employee.query.filter_by(status="active").all()
    result = []
    for emp in employees:
        orders = SalesOrder.query.filter_by(salesperson_id=emp.id).all()
        commissions = SalesCommission.query.filter_by(salesperson_id=emp.id).all()
        order_value = sum(float(o.amount or 0) for o in orders if o.status != "cancelled")
        completed = sum(1 for o in orders if o.status == "completed")
        paid_commissions = sum(float(c.amount or 0) for c in commissions if c.status == "paid")
        pending_commissions = sum(float(c.amount or 0) for c in commissions if c.status in ("pending", "approved"))
        if not orders and not commissions:
            continue
        result.append({
            "employee_id": emp.id,
            "name": emp.full_name,
            "department": emp.department,
            "position": emp.position,
            "orders_count": len(orders),
            "orders_completed": completed,
            "orders_value": round(order_value, 2),
            "commissions_count": len(commissions),
            "paid_commissions": round(paid_commissions, 2),
            "pending_commissions": round(pending_commissions, 2),
        })
    result.sort(key=lambda r: r["orders_value"], reverse=True)
    return jsonify(result)


# ============ عروض الأسعار (مشاركة مع CRM) ============

@sales_bp.route("/quotes", methods=["GET"])
@require_api("sales", "view")
def list_sales_quotes():
    quotes = Quote.query.order_by(Quote.created_at.desc()).all()
    return jsonify([q.to_dict() for q in quotes])


@sales_bp.route("/quotes/<int:quote_id>/convert", methods=["POST"])
@require_api("sales", "create")
def quote_to_order(quote_id):
    """تحويل عرض سعر → أمر بيع."""
    quote = Quote.query.get_or_404(quote_id)
    if not quote.customer_id:
        return jsonify({"message": "sales.quoteNeedsCustomer", "error_key": "sales.quoteNeedsCustomer"}), 400
    data = request.get_json() or {}
    order = SalesOrder(
        order_number=_next_number(SalesOrder, "SO", SalesOrder.order_number),
        customer_id=quote.customer_id,
        salesperson_id=data.get("salesperson_id") or None,
        quote_id=quote.id,
        financial_year_id=data.get("financial_year_id") or None,
        order_date=date.today(),
        due_date=parse_date(data.get("due_date")),
        status=data.get("status", "draft"),
        notes=quote.notes,
    )
    for item in quote.items:
        order.items.append(SalesOrderItem(
            description=item.description,
            quantity=item.qty,
            unit_price=item.unit_price,
            tax_rate=parse_float(data.get("tax_rate")),
        ))
    order.amount = round(sum(float(i.quantity or 0) * float(i.unit_price or 0)
                             * (1 + float(i.tax_rate or 0) / 100) for i in order.items), 2)
    db.session.add(order)
    if quote.status in ("draft", "sent"):
        quote.status = "accepted"
    db.session.commit()
    _log("create", "sales_order", order.id, order.order_number)
    return jsonify(order.to_dict()), 201
