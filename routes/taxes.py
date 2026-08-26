from datetime import datetime
from flask import Blueprint, request, jsonify
from database import db
from models import TaxType, Company, FinancialYear, Invoice, PurchaseOrder
from permissions import require_api
from auditlog import log_action
from utils.pdf import _base_currency_info

taxes_bp = Blueprint("taxes", __name__, url_prefix="/api/taxes")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _validate(data, partial=False):
    if not partial or "name" in data:
        if not (data.get("name") or "").strip():
            return "taxes.nameRequired"
    if not partial or "rate" in data:
        try:
            rate = float(data.get("rate") or 0)
        except (TypeError, ValueError):
            rate = -1
        if rate < 0 or rate > 100:
            return "taxes.rateInvalid"
    return None


@taxes_bp.route("", methods=["GET"])
@require_api("taxes", "view")
def list_tax_types():
    types = TaxType.query.order_by(TaxType.rate.desc()).all()
    return jsonify({"tax_types": [x.to_dict() for x in types]})


@taxes_bp.route("/defaults", methods=["GET"])
@require_api("taxes", "view")
def defaults():
    """يعيد معدل الضريبة الافتراضي للبنود الجديدة في الفواتير وأوامر الشراء."""
    import utils.settings as settings_module
    rate = settings_module.get_float("doc_default_tax_rate", None)
    if rate is not None and 0 <= rate <= 100:
        return jsonify({"default_rate": round(rate, 2), "tax_type": None})
    tax = TaxType.query.filter_by(is_default=True, is_active=True).first()
    if not tax:
        tax = TaxType.query.filter_by(is_active=True).order_by(TaxType.rate.desc()).first()
    return jsonify({"default_rate": float(tax.rate) if tax else 0.0, "tax_type": tax.to_dict() if tax else None})


@taxes_bp.route("", methods=["POST"])
@require_api("taxes", "create")
def create_tax_type():
    data = request.get_json(silent=True) or {}
    err = _validate(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    name = data["name"].strip()
    if TaxType.query.filter_by(name=name).first():
        return jsonify({"message": "taxes.duplicate", "error_key": "taxes.duplicate"}), 400
    tax = TaxType(
        name=name,
        rate=float(data.get("rate") or 0),
        is_active=bool(data.get("is_active", True)),
        is_default=bool(data.get("is_default", False)),
    )
    if tax.is_default:
        _clear_default()
    db.session.add(tax)
    db.session.commit()
    log_action("create", "tax_type", tax.id, f"نوع ضريبة: {tax.name}")
    return jsonify({"success": True, "tax_type": tax.to_dict()}), 201


@taxes_bp.route("/<int:tax_id>", methods=["PUT"])
@require_api("taxes", "edit")
def update_tax_type(tax_id):
    tax = TaxType.query.get_or_404(tax_id)
    data = request.get_json(silent=True) or {}
    err = _validate(data, partial=True)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if "name" in data:
        name = data["name"].strip()
        dup = TaxType.query.filter(TaxType.name == name, TaxType.id != tax.id).first()
        if dup:
            return jsonify({"message": "taxes.duplicate", "error_key": "taxes.duplicate"}), 400
        tax.name = name
    if "rate" in data:
        tax.rate = float(data["rate"] or 0)
    if "is_active" in data:
        tax.is_active = bool(data["is_active"])
    if "is_default" in data:
        tax.is_default = bool(data["is_default"])
        if tax.is_default:
            _clear_default(exclude=tax.id)
    db.session.commit()
    log_action("update", "tax_type", tax.id, f"نوع ضريبة: {tax.name}")
    return jsonify({"success": True, "tax_type": tax.to_dict()})


@taxes_bp.route("/<int:tax_id>", methods=["DELETE"])
@require_api("taxes", "delete")
def delete_tax_type(tax_id):
    tax = TaxType.query.get_or_404(tax_id)
    name = tax.name
    db.session.delete(tax)
    db.session.commit()
    log_action("delete", "tax_type", tax_id, f"نوع ضريبة: {name}")
    return jsonify({"success": True})


def _clear_default(exclude=None):
    for t in TaxType.query.filter_by(is_default=True).all():
        if exclude and t.id == exclude:
            continue
        t.is_default = False


def _doc_tax(doc, items):
    """حساب الوعاء والضريبة لمستند من بنوده."""
    base = 0.0
    tax = 0.0
    rates = {}
    for it in items:
        line = float(it.quantity or 0) * float(it.unit_price or 0)
        rate = float(it.tax_rate or 0)
        t = line * rate / 100
        base += line
        tax += t
        rates[rate] = rates.get(rate, 0.0) + t
    return base, tax, rates


def compute_tax_report(year_id=None, start=None, end=None, company_id=None):
    """ينتج تقرير ضرائب: ضريبة مبيعات/مشتريات وصافي + تفصيل حسب المعدل + قائمة مستندات."""
    year = None
    if year_id:
        year = db.session.get(FinancialYear, year_id)
    if year:
        start, end = year.start_date, year.end_date
        company_id = company_id or year.company_id

    if not start and not end:
        active = FinancialYear.query.filter_by(is_active=True).order_by(FinancialYear.start_date.desc()).first()
        if active:
            start, end = active.start_date, active.end_date

    q_inv = Invoice.query
    q_po = PurchaseOrder.query
    if year:
        q_inv = q_inv.filter_by(financial_year_id=year.id)
        q_po = q_po.filter_by(financial_year_id=year.id)
    else:
        if start and end:
            q_inv = q_inv.filter(Invoice.issue_date.isnot(None), Invoice.issue_date >= start, Invoice.issue_date <= end)
            q_po = q_po.filter(PurchaseOrder.order_date.isnot(None), PurchaseOrder.order_date >= start, PurchaseOrder.order_date <= end)
        elif start:
            q_inv = q_inv.filter(Invoice.issue_date.isnot(None), Invoice.issue_date >= start)
            q_po = q_po.filter(PurchaseOrder.order_date.isnot(None), PurchaseOrder.order_date >= start)
        elif end:
            q_inv = q_inv.filter(Invoice.issue_date.isnot(None), Invoice.issue_date <= end)
            q_po = q_po.filter(PurchaseOrder.order_date.isnot(None), PurchaseOrder.order_date <= end)
    if company_id and not year:
        q_inv = q_inv.filter(Invoice.financial_year.has(company_id=company_id))
        q_po = q_po.filter(PurchaseOrder.financial_year.has(company_id=company_id))

    output_base = output_tax = 0.0
    input_base = input_tax = 0.0
    out_by_rate = {}
    in_by_rate = {}
    documents = []

    for inv in q_inv.filter_by(invoice_type="sales").all():
        base, tax, rates = _doc_tax(inv, inv.items)
        output_base += base
        output_tax += tax
        for r, v in rates.items():
            out_by_rate[r] = out_by_rate.get(r, 0.0) + v
        documents.append({
            "kind": "sales", "number": inv.invoice_number,
            "date": inv.issue_date.isoformat() if inv.issue_date else None,
            "party": inv.customer.full_name if inv.customer else "—",
            "base": round(base, 2), "tax": round(tax, 2), "rates": sorted(rates),
        })

    for inv in q_inv.filter(Invoice.invoice_type.in_(["purchase", "expense"])).all():
        base, tax, rates = _doc_tax(inv, inv.items)
        input_base += base
        input_tax += tax
        for r, v in rates.items():
            in_by_rate[r] = in_by_rate.get(r, 0.0) + v
        documents.append({
            "kind": "purchase" if inv.invoice_type == "purchase" else "expense",
            "number": inv.invoice_number,
            "date": inv.issue_date.isoformat() if inv.issue_date else None,
            "party": inv.supplier.company_name if inv.supplier else "—",
            "base": round(base, 2), "tax": round(tax, 2), "rates": sorted(rates),
        })

    for po in q_po.all():
        base, tax, rates = _doc_tax(po, po.items)
        input_base += base
        input_tax += tax
        for r, v in rates.items():
            in_by_rate[r] = in_by_rate.get(r, 0.0) + v
        documents.append({
            "kind": "po", "number": po.po_number,
            "date": po.order_date.isoformat() if po.order_date else None,
            "party": po.supplier.company_name if po.supplier else "—",
            "base": round(base, 2), "tax": round(tax, 2), "rates": sorted(rates),
        })

    documents.sort(key=lambda d: d["date"] or "")

    rates_keys = sorted(set(list(out_by_rate) + list(in_by_rate)), reverse=True)
    breakdown = []
    for r in rates_keys:
        ob, ib = out_by_rate.get(r, 0.0), in_by_rate.get(r, 0.0)
        ob_docs = len([d for d in documents if d["kind"] in ("sales",) and r in d["rates"]])
        ib_docs = len([d for d in documents if d["kind"] in ("purchase", "po", "expense") and r in d["rates"]])
        breakdown.append({
            "rate": r,
            "output_base": round(ob / (r / 100), 2) if r else round(ob, 2),
            "output_tax": round(ob, 2),
            "input_base": round(ib / (r / 100), 2) if r else round(ib, 2),
            "input_tax": round(ib, 2),
            "net": round(ob - ib, 2),
            "output_docs": ob_docs,
            "input_docs": ib_docs,
        })

    company = None
    currency = None
    if year:
        company = year.company
        currency = _base_currency_info(year)
    elif company_id:
        company = db.session.get(Company, company_id)
        currency = _base_currency_info(company) if company else None

    return {
        "company_name": company.name if company else None,
        "company_tax_number": company.tax_number if company else None,
        "period": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
        "currency": currency,
        "output_base": round(output_base, 2),
        "output_tax": round(output_tax, 2),
        "output_docs": len([d for d in documents if d["kind"] == "sales"]),
        "input_base": round(input_base, 2),
        "input_tax": round(input_tax, 2),
        "input_docs": len([d for d in documents if d["kind"] in ("purchase", "po", "expense")]),
        "net_tax": round(output_tax - input_tax, 2),
        "documents_count": len(documents),
        "breakdown": breakdown,
        "documents": documents,
    }


@taxes_bp.route("/report", methods=["GET"])
@require_api("taxes", "view")
def report():
    year_id = request.args.get("year_id", type=int)
    company_id = request.args.get("company_id", type=int)
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    if not year_id and not start and not end:
        active = FinancialYear.query.filter_by(is_active=True).order_by(FinancialYear.start_date.desc()).first()
        if not active:
            return jsonify({"message": "taxes.periodRequired", "error_key": "taxes.periodRequired"}), 400
    return jsonify(compute_tax_report(year_id=year_id, start=start, end=end, company_id=company_id))
