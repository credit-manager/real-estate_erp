from flask import Blueprint, request, jsonify
from datetime import datetime
from database import db
from models import (
    PurchaseRequest, PurchaseRequestItem,
    RFQ, RFQItem, RFQQuote, RFQQuoteItem,
    PurchaseReceiving, PurchaseReceivingItem,
    PurchaseReturn, PurchaseReturnItem,
    PurchaseOrder, Supplier, Project,
)
from permissions import require_api
from routes.financial_years import financial_year_error
from utils.pagination import paged_or_cap

procurement_bp = Blueprint("procurement", __name__, url_prefix="/api/procurement")


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


def _next_number(prefix, model, field):
    from utils.docnum import seq_after_max
    return seq_after_max(model, prefix + "-{n:04d}")


# ============ طلبات الشراء (Purchase Requests) ============

@procurement_bp.route("/purchase-requests", methods=["GET"])
@require_api("procurement", "view")
def list_purchase_requests():
    q = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@procurement_bp.route("/purchase-requests", methods=["POST"])
@require_api("procurement", "create")
def create_purchase_request():
    data = request.get_json() or {}
    pr = PurchaseRequest(
        pr_number=data.get("pr_number") or _next_number("PR", PurchaseRequest, "pr_number"),
        title=data.get("title"),
        requester=data.get("requester"),
        department=data.get("department"),
        project_id=data.get("project_id"),
        request_date=parse_date(data.get("request_date")) or datetime.now().date(),
        needed_date=parse_date(data.get("needed_date")),
        notes=data.get("notes"),
        status=data.get("status", "draft"),
    )
    # إضافة البنود
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        pr.items.append(PurchaseRequestItem(
            description=it["description"],
            quantity=float(it.get("quantity", 1) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
        ))
    pr.total = sum(float(i.quantity or 0) * float(i.unit_price or 0)
                   * (1 + float(i.tax_rate or 0) / 100) for i in pr.items)
    db.session.add(pr)
    db.session.commit()
    _log("create", "purchase_request", pr.id, pr.pr_number)
    return jsonify(pr.to_dict()), 201


@procurement_bp.route("/purchase-requests/<int:pr_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_purchase_request(pr_id):
    pr = PurchaseRequest.query.get_or_404(pr_id)
    data = request.get_json() or {}
    for field in ["pr_number", "title", "requester", "department", "project_id",
                  "notes", "status"]:
        if field in data:
            setattr(pr, field, data[field])
    if "request_date" in data:
        pr.request_date = parse_date(data["request_date"])
    if "needed_date" in data:
        pr.needed_date = parse_date(data["needed_date"])
    if "items" in data:
        pr.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            pr.items.append(PurchaseRequestItem(
                description=it["description"],
                quantity=float(it.get("quantity", 1) or 0),
                unit_price=float(it.get("unit_price", 0) or 0),
                tax_rate=float(it.get("tax_rate", 0) or 0),
            ))
        pr.total = sum(float(i.quantity or 0) * float(i.unit_price or 0)
                       * (1 + float(i.tax_rate or 0) / 100) for i in pr.items)
    db.session.commit()
    _log("update", "purchase_request", pr.id, pr.pr_number)
    return jsonify(pr.to_dict())


@procurement_bp.route("/purchase-requests/<int:pr_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_purchase_request(pr_id):
    pr = PurchaseRequest.query.get_or_404(pr_id)
    num = pr.pr_number
    db.session.delete(pr)
    db.session.commit()
    _log("delete", "purchase_request", pr_id, num)
    return jsonify({"success": True})


@procurement_bp.route("/purchase-requests/<int:pr_id>/submit", methods=["POST"])
@require_api("procurement", "edit")
def submit_purchase_request(pr_id):
    pr = PurchaseRequest.query.get_or_404(pr_id)
    pr.status = "submitted"
    db.session.commit()
    _log("submit", "purchase_request", pr.id, pr.pr_number)
    return jsonify(pr.to_dict())


@procurement_bp.route("/purchase-requests/<int:pr_id>/approve", methods=["POST"])
@require_api("procurement", "edit")
def approve_purchase_request(pr_id):
    pr = PurchaseRequest.query.get_or_404(pr_id)
    pr.status = "approved"
    db.session.commit()
    _log("approve", "purchase_request", pr.id, pr.pr_number)
    return jsonify(pr.to_dict())


@procurement_bp.route("/purchase-requests/<int:pr_id>/reject", methods=["POST"])
@require_api("procurement", "edit")
def reject_purchase_request(pr_id):
    pr = PurchaseRequest.query.get_or_404(pr_id)
    pr.status = "rejected"
    db.session.commit()
    _log("reject", "purchase_request", pr.id, pr.pr_number)
    return jsonify(pr.to_dict())


@procurement_bp.route("/purchase-requests/<int:pr_id>/convert-to-rfq", methods=["POST"])
@require_api("procurement", "create")
def convert_pr_to_rfq(pr_id):
    """تحويل طلب شراء إلى طلب عروض أسعار."""
    pr = PurchaseRequest.query.get_or_404(pr_id)
    rfq = RFQ(
        rfq_number=_next_number("RFQ", RFQ, "rfq_number"),
        title=pr.title or f"طلب عروض من {pr.pr_number}",
        project_id=pr.project_id,
        request_date=datetime.now().date(),
        notes=pr.notes,
        status="draft",
    )
    for it in pr.items:
        rfq.items.append(RFQItem(
            description=it.description,
            quantity=it.quantity,
        ))
    db.session.add(rfq)
    db.session.commit()
    _log("create", "rfq", rfq.id, rfq.rfq_number)
    return jsonify(rfq.to_dict()), 201


# ============ طلبات عروض الأسعار (RFQ) ============

@procurement_bp.route("/rfqs", methods=["GET"])
@require_api("procurement", "view")
def list_rfqs():
    q = RFQ.query.order_by(RFQ.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@procurement_bp.route("/rfqs", methods=["POST"])
@require_api("procurement", "create")
def create_rfq():
    data = request.get_json() or {}
    rfq = RFQ(
        rfq_number=data.get("rfq_number") or _next_number("RFQ", RFQ, "rfq_number"),
        title=data.get("title"),
        project_id=data.get("project_id"),
        request_date=parse_date(data.get("request_date")) or datetime.now().date(),
        deadline=parse_date(data.get("deadline")),
        notes=data.get("notes"),
        status=data.get("status", "draft"),
    )
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        rfq.items.append(RFQItem(
            description=it["description"],
            quantity=float(it.get("quantity", 1) or 0),
        ))
    db.session.add(rfq)
    db.session.commit()
    _log("create", "rfq", rfq.id, rfq.rfq_number)
    return jsonify(rfq.to_dict()), 201


@procurement_bp.route("/rfqs/<int:rfq_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_rfq(rfq_id):
    rfq = RFQ.query.get_or_404(rfq_id)
    data = request.get_json() or {}
    for field in ["rfq_number", "title", "project_id", "notes", "status"]:
        if field in data:
            setattr(rfq, field, data[field])
    if "request_date" in data:
        rfq.request_date = parse_date(data["request_date"])
    if "deadline" in data:
        rfq.deadline = parse_date(data["deadline"])
    if "items" in data:
        rfq.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            rfq.items.append(RFQItem(
                description=it["description"],
                quantity=float(it.get("quantity", 1) or 0),
            ))
    db.session.commit()
    _log("update", "rfq", rfq.id, rfq.rfq_number)
    return jsonify(rfq.to_dict())


@procurement_bp.route("/rfqs/<int:rfq_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_rfq(rfq_id):
    rfq = RFQ.query.get_or_404(rfq_id)
    num = rfq.rfq_number
    db.session.delete(rfq)
    db.session.commit()
    _log("delete", "rfq", rfq_id, num)
    return jsonify({"success": True})


@procurement_bp.route("/rfqs/<int:rfq_id>/send", methods=["POST"])
@require_api("procurement", "edit")
def send_rfq(rfq_id):
    rfq = RFQ.query.get_or_404(rfq_id)
    rfq.status = "sent"
    db.session.commit()
    _log("update", "rfq", rfq.id, f"{rfq.rfq_number} -> sent")
    return jsonify(rfq.to_dict())


@procurement_bp.route("/rfqs/<int:rfq_id>/close", methods=["POST"])
@require_api("procurement", "edit")
def close_rfq(rfq_id):
    rfq = RFQ.query.get_or_404(rfq_id)
    rfq.status = "closed"
    db.session.commit()
    _log("update", "rfq", rfq.id, f"{rfq.rfq_number} -> closed")
    return jsonify(rfq.to_dict())


# ============ عروض الموردين (RFQ Quotes) ============

@procurement_bp.route("/rfqs/<int:rfq_id>/quotes", methods=["GET"])
@require_api("procurement", "view")
def list_rfq_quotes(rfq_id):
    quotes = RFQQuote.query.filter_by(rfq_id=rfq_id).all()
    return jsonify([q.to_dict() for q in quotes])


@procurement_bp.route("/rfqs/<int:rfq_id>/quotes", methods=["POST"])
@require_api("procurement", "create")
def create_rfq_quote(rfq_id):
    data = request.get_json() or {}
    quote = RFQQuote(
        rfq_id=rfq_id,
        supplier_id=data.get("supplier_id"),
        delivery_days=data.get("delivery_days", 0),
        notes=data.get("notes"),
    )
    # إضافة بنود العرض
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        quote.items.append(RFQQuoteItem(
            rfq_item_id=it.get("rfq_item_id"),
            description=it["description"],
            quantity=float(it.get("quantity", 1) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
        ))
    db.session.add(quote)
    db.session.commit()
    _log("create", "rfq_quote", quote.id, f"RFQ={rfq_id} supplier={quote.supplier_id}")
    return jsonify(quote.to_dict()), 201


@procurement_bp.route("/rfq-quotes/<int:quote_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_rfq_quote(quote_id):
    quote = RFQQuote.query.get_or_404(quote_id)
    data = request.get_json() or {}
    for field in ["supplier_id", "delivery_days", "notes", "is_winner"]:
        if field in data:
            setattr(quote, field, data[field])
    if "items" in data:
        quote.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            quote.items.append(RFQQuoteItem(
                rfq_item_id=it.get("rfq_item_id"),
                description=it["description"],
                quantity=float(it.get("quantity", 1) or 0),
                unit_price=float(it.get("unit_price", 0) or 0),
                tax_rate=float(it.get("tax_rate", 0) or 0),
            ))
    db.session.commit()
    _log("update", "rfq_quote", quote.id, f"quote={quote.id}")
    return jsonify(quote.to_dict())


@procurement_bp.route("/rfq-quotes/<int:quote_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_rfq_quote(quote_id):
    quote = RFQQuote.query.get_or_404(quote_id)
    db.session.delete(quote)
    db.session.commit()
    _log("delete", "rfq_quote", quote_id, f"quote={quote_id}")
    return jsonify({"success": True})


@procurement_bp.route("/rfq-quotes/<int:quote_id>/select-winner", methods=["POST"])
@require_api("procurement", "edit")
def select_winner(quote_id):
    """اختيار عرض فائز — يُلغى اختيار أي عرض آخر لنفس الـ RFQ."""
    quote = RFQQuote.query.get_or_404(quote_id)
    # إلغاء الفائزين السابقين لنفس الـ RFQ
    for q in RFQQuote.query.filter_by(rfq_id=quote.rfq_id).all():
        q.is_winner = False
    quote.is_winner = True
    db.session.commit()
    _log("update", "rfq_quote", quote.id, f"winner selected for RFQ={quote.rfq_id}")
    return jsonify(quote.to_dict())


@procurement_bp.route("/rfqs/<int:rfq_id>/compare", methods=["GET"])
@require_api("procurement", "view")
def compare_rfq_quotes(rfq_id):
    """مقارنة عروض الأسعار لنفس طلب عروض الأسعار."""
    rfq = RFQ.query.get_or_404(rfq_id)
    quotes = RFQQuote.query.filter_by(rfq_id=rfq_id).all()
    items = rfq.items

    comparison = []
    for item in items:
        row = {
            "item_id": item.id,
            "description": item.description,
            "quantity": float(item.quantity or 0),
            "quotes": [],
        }
        for q in quotes:
            q_item = next((qi for qi in q.items if qi.rfq_item_id == item.id), None)
            row["quotes"].append({
                "quote_id": q.id,
                "supplier_id": q.supplier_id,
                "supplier_name": q.supplier.company_name if q.supplier else None,
                "unit_price": float(q_item.unit_price or 0) if q_item else 0,
                "tax_rate": float(q_item.tax_rate or 0) if q_item else 0,
                "total": float(q_item.quantity or 0) * float(q_item.unit_price or 0)
                         * (1 + float(q_item.tax_rate or 0) / 100) if q_item else 0,
                "is_winner": bool(q.is_winner),
            })
        comparison.append(row)

    return jsonify({
        "rfq_id": rfq.id,
        "rfq_number": rfq.rfq_number,
        "title": rfq.title,
        "quotes": [q.to_dict() for q in quotes],
        "comparison": comparison,
    })


# ============ الاستلام (Receiving) ============

@procurement_bp.route("/receivings", methods=["GET"])
@require_api("procurement", "view")
def list_receivings():
    q = PurchaseReceiving.query.order_by(PurchaseReceiving.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@procurement_bp.route("/receivings", methods=["POST"])
@require_api("procurement", "create")
def create_receiving():
    data = request.get_json() or {}
    receiving = PurchaseReceiving(
        receiving_number=data.get("receiving_number") or _next_number("RCV", PurchaseReceiving, "receiving_number"),
        po_id=data.get("po_id"),
        received_date=parse_date(data.get("received_date")) or datetime.now().date(),
        warehouse=data.get("warehouse"),
        notes=data.get("notes"),
        status=data.get("status", "received"),
    )
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        receiving.items.append(PurchaseReceivingItem(
            description=it["description"],
            quantity=float(it.get("quantity", 0) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
        ))
    db.session.add(receiving)
    db.session.commit()
    # تحديث حالة أمر الشراء إلى delivered
    if receiving.po_id:
        po = db.session.get(PurchaseOrder, receiving.po_id)
        if po and po.status == "approved":
            po.status = "delivered"
            db.session.commit()
    _log("create", "receiving", receiving.id, receiving.receiving_number)
    return jsonify(receiving.to_dict()), 201


@procurement_bp.route("/receivings/<int:receiving_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_receiving(receiving_id):
    receiving = PurchaseReceiving.query.get_or_404(receiving_id)
    data = request.get_json() or {}
    for field in ["receiving_number", "po_id", "warehouse", "notes", "status"]:
        if field in data:
            setattr(receiving, field, data[field])
    if "received_date" in data:
        receiving.received_date = parse_date(data["received_date"])
    if "items" in data:
        receiving.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            receiving.items.append(PurchaseReceivingItem(
                description=it["description"],
                quantity=float(it.get("quantity", 0) or 0),
                unit_price=float(it.get("unit_price", 0) or 0),
                tax_rate=float(it.get("tax_rate", 0) or 0),
            ))
    db.session.commit()
    _log("update", "receiving", receiving.id, receiving.receiving_number)
    return jsonify(receiving.to_dict())


@procurement_bp.route("/receivings/<int:receiving_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_receiving(receiving_id):
    receiving = PurchaseReceiving.query.get_or_404(receiving_id)
    num = receiving.receiving_number
    db.session.delete(receiving)
    db.session.commit()
    _log("delete", "receiving", receiving_id, num)
    return jsonify({"success": True})


# ============ مرتجعات الشراء (Purchase Returns) ============

@procurement_bp.route("/returns", methods=["GET"])
@require_api("procurement", "view")
def list_returns():
    q = PurchaseReturn.query.order_by(PurchaseReturn.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@procurement_bp.route("/returns", methods=["POST"])
@require_api("procurement", "create")
def create_return():
    data = request.get_json() or {}
    ret = PurchaseReturn(
        return_number=data.get("return_number") or _next_number("RET", PurchaseReturn, "return_number"),
        po_id=data.get("po_id"),
        supplier_id=data.get("supplier_id"),
        return_date=parse_date(data.get("return_date")) or datetime.now().date(),
        reason=data.get("reason"),
        status=data.get("status", "draft"),
    )
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        ret.items.append(PurchaseReturnItem(
            description=it["description"],
            quantity=float(it.get("quantity", 0) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
        ))
    ret.total = sum(float(i.quantity or 0) * float(i.unit_price or 0)
                    * (1 + float(i.tax_rate or 0) / 100) for i in ret.items)
    db.session.add(ret)
    db.session.commit()
    _log("create", "purchase_return", ret.id, ret.return_number)
    return jsonify(ret.to_dict()), 201


@procurement_bp.route("/returns/<int:return_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_return(return_id):
    ret = PurchaseReturn.query.get_or_404(return_id)
    data = request.get_json() or {}
    for field in ["return_number", "po_id", "supplier_id", "reason", "status"]:
        if field in data:
            setattr(ret, field, data[field])
    if "return_date" in data:
        ret.return_date = parse_date(data["return_date"])
    if "items" in data:
        ret.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            ret.items.append(PurchaseReturnItem(
                description=it["description"],
                quantity=float(it.get("quantity", 0) or 0),
                unit_price=float(it.get("unit_price", 0) or 0),
                tax_rate=float(it.get("tax_rate", 0) or 0),
            ))
        ret.total = sum(float(i.quantity or 0) * float(i.unit_price or 0)
                        * (1 + float(i.tax_rate or 0) / 100) for i in ret.items)
    db.session.commit()
    _log("update", "purchase_return", ret.id, ret.return_number)
    return jsonify(ret.to_dict())


@procurement_bp.route("/returns/<int:return_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_return(return_id):
    ret = PurchaseReturn.query.get_or_404(return_id)
    num = ret.return_number
    db.session.delete(ret)
    db.session.commit()
    _log("delete", "purchase_return", return_id, num)
    return jsonify({"success": True})


@procurement_bp.route("/returns/<int:return_id>/process", methods=["POST"])
@require_api("procurement", "edit")
def process_return(return_id):
    ret = PurchaseReturn.query.get_or_404(return_id)
    ret.status = "processed"
    db.session.commit()
    _log("update", "purchase_return", ret.id, f"{ret.return_number} -> processed")
    return jsonify(ret.to_dict())


@procurement_bp.route("/returns/<int:return_id>/complete", methods=["POST"])
@require_api("procurement", "edit")
def complete_return(return_id):
    ret = PurchaseReturn.query.get_or_404(return_id)
    ret.status = "completed"
    db.session.commit()
    _log("update", "purchase_return", ret.id, f"{ret.return_number} -> completed")
    return jsonify(ret.to_dict())


# ============ فواتير الموردين (Supplier Invoices) ============

@procurement_bp.route("/supplier-invoices", methods=["GET"])
@require_api("procurement", "view")
def list_supplier_invoices():
    """فواتير الموردين — تُقرأ من جدول الفواتير بنوع purchase."""
    from models import Invoice
    q = Invoice.query.filter_by(invoice_type="purchase").order_by(Invoice.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@procurement_bp.route("/supplier-invoices", methods=["POST"])
@require_api("procurement", "create")
def create_supplier_invoice():
    """إنشاء فاتورة مورد."""
    from models import Invoice, InvoiceItem
    from routes.financial_years import financial_year_error
    data = request.get_json() or {}
    fy_id = data.get("financial_year_id")
    if fy_id in (None, "", 0):
        fy_id = None
    else:
        err = financial_year_error(fy_id)
        if err:
            return jsonify({"message": err, "error_key": err}), 400

    invoice = Invoice(
        invoice_number=data.get("invoice_number"),
        invoice_type="purchase",
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
    # إضافة البنود
    for it in (data.get("items") or []):
        if not isinstance(it, dict) or not (it.get("description") or "").strip():
            continue
        invoice.items.append(InvoiceItem(
            item_id=it.get("item_id"),
            warehouse_id=it.get("warehouse_id"),
            description=it["description"],
            quantity=float(it.get("quantity", 1) or 0),
            unit_price=float(it.get("unit_price", 0) or 0),
            tax_rate=float(it.get("tax_rate", 0) or 0),
            expiry_date=parse_date(it.get("expiry_date")),
        ))
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
                    is_receipt=False,
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


@procurement_bp.route("/supplier-invoices/<int:invoice_id>", methods=["PUT"])
@require_api("procurement", "edit")
def update_supplier_invoice(invoice_id):
    from models import Invoice, InvoiceItem
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.invoice_type != "purchase":
        return jsonify({"error": "not_supplier_invoice"}), 400
    data = request.get_json() or {}
    from utils.stock import reverse_purchase_invoice
    reverse_purchase_invoice(invoice)
    for field in ["invoice_number", "supplier_id", "project_id", "paid_amount",
                  "status", "description"]:
        if field in data:
            setattr(invoice, field, data[field])
    if "amount" in data and "items" not in data:
        invoice.amount = data["amount"]
    if "issue_date" in data:
        invoice.issue_date = parse_date(data["issue_date"])
    if "due_date" in data:
        invoice.due_date = parse_date(data["due_date"])
    if "items" in data:
        invoice.items = []
        for it in data["items"]:
            if not isinstance(it, dict) or not (it.get("description") or "").strip():
                continue
            invoice.items.append(InvoiceItem(
                item_id=it.get("item_id"),
                warehouse_id=it.get("warehouse_id"),
                description=it["description"],
                quantity=float(it.get("quantity", 1) or 0),
                unit_price=float(it.get("unit_price", 0) or 0),
                tax_rate=float(it.get("tax_rate", 0) or 0),
                expiry_date=parse_date(it.get("expiry_date")),
            ))
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
                    is_receipt=False,
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


@procurement_bp.route("/supplier-invoices/<int:invoice_id>", methods=["DELETE"])
@require_api("procurement", "delete")
def delete_supplier_invoice(invoice_id):
    from models import Invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.invoice_type != "purchase":
        return jsonify({"error": "not_supplier_invoice"}), 400
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