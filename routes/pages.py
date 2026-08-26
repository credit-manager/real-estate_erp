from flask import Blueprint, render_template, redirect, url_for, session, send_file, request
from io import BytesIO
import datetime
from routes.auth import login_required
from permissions import require_page, admin_required
from database import db
from models import User, Invoice, RentalContract, PurchaseOrder, FinancialYear, PaymentPlan, Quote, CrmContract, SalesOrder, SalesReturn
from i18n import get_lang
import utils.settings as settings_module
from utils.pdf import (
build_invoice_pdf, build_po_pdf, build_contract_pdf, build_financial_year_report_pdf,
build_tax_report_pdf, build_crm_quote_pdf, build_crm_contract_pdf,
build_sales_order_pdf, build_sales_return_pdf,
)
from routes.taxes import compute_tax_report


def _fmt_date(d):
    fmt = settings_module.get("date_format", "dd/mm/yyyy")
    if not d:
        return "—"
    return d.strftime("%Y-%m-%d") if fmt == "yyyy-mm-dd" else d.strftime("%d/%m/%Y")


def _fmt_money(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        f = 0
    dec = settings_module.get_int("number_decimals", 2)
    return f"{f:,.{dec}f}"

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/dashboard")
@require_page("dashboard")
def dashboard():
    return render_template("dashboard.html", full_name=session.get("full_name", ""))


@pages_bp.route("/projects")
@require_page("projects")
def projects():
    return render_template("projects.html")


@pages_bp.route("/projects/map")
@require_page("projects")
def project_map():
    return render_template("project_map.html")


@pages_bp.route("/finance")
@require_page("finance")
def finance():
    return render_template("finance.html")


@pages_bp.route("/procurement")
@require_page("procurement")
def procurement():
    return render_template("procurement.html")


@pages_bp.route("/sales")
@require_page("sales")
def sales():
    return render_template("sales.html")


@pages_bp.route("/hr")
@require_page("hr")
def hr():
    return render_template("hr.html")


@pages_bp.route("/real-estate")
@require_page("realestate")
def real_estate():
    return render_template("real-estate.html")


@pages_bp.route("/rentals")
@require_page("rentals")
def rentals():
    return render_template("rentals.html")


@pages_bp.route("/crm")
@require_page("crm")
def crm():
    return render_template("crm.html")


@pages_bp.route("/reports")
@require_page("reports")
def reports():
    return render_template("reports.html")


@pages_bp.route("/users")
@require_page("users")
def users():
    return render_template("users.html")


@pages_bp.route("/roles")
@require_page("roles")
def roles():
    return render_template("roles.html")


@pages_bp.route("/companies")
@require_page("companies")
def companies():
    return render_template("companies.html")


@pages_bp.route("/financial-years")
@require_page("financial_years")
def financial_years():
    return render_template("financial_years.html")


@pages_bp.route("/currencies")
@require_page("currencies")
def currencies():
    return render_template("currencies.html")


@pages_bp.route("/taxes")
@require_page("taxes")
def taxes():
    return render_template("taxes.html")


@pages_bp.route("/permission-denied")
@login_required
def permission_denied():
    return render_template("permission_denied.html"), 403


@pages_bp.route("/change-password")
@login_required
def change_password():
    return render_template("change_password.html")


@pages_bp.route("/profile")
@login_required
def profile():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("profile.html", user=user)


@pages_bp.route("/audit")
@require_page("audit")
def audit():
    return render_template("audit.html")


@pages_bp.route("/backup")
@require_page("backup")
def backup():
    return render_template("backup.html")


@pages_bp.route("/documents/invoice/<int:invoice_id>")
@require_page("finance")
def print_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    party = None
    if invoice.invoice_type == "sales" and invoice.customer:
        party = {
            "name": invoice.customer.full_name,
            "phone": invoice.customer.phone,
            "email": invoice.customer.email,
            "address": invoice.customer.address,
        }
    elif invoice.supplier:
        party = {
            "name": invoice.supplier.company_name,
            "phone": invoice.supplier.phone,
            "email": invoice.supplier.email,
            "address": invoice.supplier.address,
        }
    items = []
    subtotal = 0.0
    total_tax = 0.0
    for it in invoice.items:
        line = float(it.quantity or 0) * float(it.unit_price or 0)
        tax = line * float(it.tax_rate or 0) / 100
        subtotal += line
        total_tax += tax
        items.append({
            "description": it.description,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "tax_rate": it.tax_rate,
            "line": line,
            "tax": tax,
            "total": line + tax,
        })
    company = invoice.financial_year.company if invoice.financial_year else None
    return render_template(
        "print_invoice.html",
        invoice=invoice,
        party=party,
        project_name=invoice.project.name if invoice.project else None,
        company_name=company.name if company else None,
        company_tax_number=company.tax_number if company else None,
        items=items,
        subtotal=subtotal,
        total_tax=total_tax,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/po/<int:po_id>")
@require_page("procurement")
def print_po(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    items = []
    subtotal = 0.0
    total_tax = 0.0
    for it in po.items:
        line = float(it.quantity or 0) * float(it.unit_price or 0)
        tax = line * float(it.tax_rate or 0) / 100
        subtotal += line
        total_tax += tax
        items.append({
            "description": it.description,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "tax_rate": it.tax_rate,
            "line": line,
            "tax": tax,
            "total": line + tax,
        })
    return render_template(
        "print_po.html",
        po=po,
        supplier=po.supplier,
        project_name=po.project.name if po.project else None,
        items=items,
        subtotal=subtotal,
        total_tax=total_tax,
        fmt=_fmt_date,
        money=_fmt_money,
    )


def _pdf_response(data, filename):
    return send_file(
        BytesIO(bytes(data)),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@pages_bp.route("/documents/invoice/<int:invoice_id>/pdf")
@require_page("finance")
def download_invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return _pdf_response(build_invoice_pdf(invoice, get_lang()),
                         f"invoice-{invoice.invoice_number}.pdf")


@pages_bp.route("/documents/po/<int:po_id>/pdf")
@require_page("procurement")
def download_po_pdf(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    return _pdf_response(build_po_pdf(po, get_lang()),
                         f"po-{po.po_number}.pdf")


@pages_bp.route("/documents/sales-order/<int:order_id>")
@require_page("sales")
def print_sales_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    party = None
    if order.customer:
        c = order.customer
        party = {"name": c.full_name, "phone": c.phone, "email": c.email, "address": c.address}
    items = []
    subtotal = 0.0
    total_tax = 0.0
    for it in order.items:
        line = float(it.quantity or 0) * float(it.unit_price or 0)
        tax = line * float(it.tax_rate or 0) / 100
        subtotal += line
        total_tax += tax
        items.append({
            "description": it.description,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "tax_rate": it.tax_rate,
            "line": line,
            "tax": tax,
            "total": line + tax,
        })
    company = order.financial_year.company if order.financial_year else None
    return render_template(
        "print_sales_order.html",
        order=order,
        party=party,
        salesperson=order.salesperson,
        company_name=company.name if company else None,
        company_tax_number=company.tax_number if company else None,
        items=items,
        subtotal=subtotal,
        total_tax=total_tax,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/sales-order/<int:order_id>/pdf")
@require_page("sales")
def download_sales_order_pdf(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    return _pdf_response(build_sales_order_pdf(order, get_lang()),
                         f"sales-order-{order.order_number}.pdf")


@pages_bp.route("/documents/sales-return/<int:return_id>")
@require_page("sales")
def print_sales_return(return_id):
    ret = SalesReturn.query.get_or_404(return_id)
    party = None
    if ret.customer:
        c = ret.customer
        party = {"name": c.full_name, "phone": c.phone, "email": c.email, "address": c.address}
    items = []
    subtotal = 0.0
    total_tax = 0.0
    for it in ret.items:
        line = float(it.quantity or 0) * float(it.unit_price or 0)
        tax = line * float(it.tax_rate or 0) / 100
        subtotal += line
        total_tax += tax
        items.append({
            "description": it.description,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "tax_rate": it.tax_rate,
            "line": line,
            "tax": tax,
            "total": line + tax,
        })
    company = ret.financial_year.company if ret.financial_year else None
    return render_template(
        "print_sales_return.html",
        ret=ret,
        party=party,
        company_name=company.name if company else None,
        company_tax_number=company.tax_number if company else None,
        items=items,
        subtotal=subtotal,
        total_tax=total_tax,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/sales-return/<int:return_id>/pdf")
@require_page("sales")
def download_sales_return_pdf(return_id):
    ret = SalesReturn.query.get_or_404(return_id)
    return _pdf_response(build_sales_return_pdf(ret, get_lang()),
                         f"sales-return-{ret.return_number}.pdf")


@pages_bp.route("/documents/contract/<int:rental_id>/pdf")
@require_page("rentals")
def download_contract_pdf(rental_id):
    contract = RentalContract.query.get_or_404(rental_id)
    return _pdf_response(build_contract_pdf(contract, get_lang()),
                         f"contract-{contract.contract_number}.pdf")


@pages_bp.route("/documents/financial-year/<int:year_id>/pdf")
@require_page("financial_years")
def download_financial_year_pdf(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    return _pdf_response(build_financial_year_report_pdf(year, get_lang()),
                         f"financial-year-{year.name}.pdf")


@pages_bp.route("/documents/tax-report/pdf")
@require_page("taxes")
def download_tax_report_pdf():
    from datetime import datetime
    year_id = request.args.get("year_id", type=int)
    company_id = request.args.get("company_id", type=int)
    start = end = None
    for key in ("start", "end"):
        val = request.args.get(key)
        if val:
            try:
                parsed = datetime.strptime(val, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            if key == "start":
                start = parsed
            else:
                end = parsed
    report = compute_tax_report(year_id=year_id, start=start, end=end, company_id=company_id)
    filename = "tax-report-" + (report.get("company_name") or "all") + ".pdf"
    return _pdf_response(build_tax_report_pdf(report, get_lang()), filename)


@pages_bp.route("/documents/contract/<int:rental_id>")
@require_page("rentals")
def print_contract(rental_id):
    contract = RentalContract.query.get_or_404(rental_id)
    unit = contract.unit
    return render_template(
        "print_contract.html",
        contract=contract,
        unit=unit,
        project_name=unit.project.name if unit and unit.project else None,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/crm-quote/<int:quote_id>")
@require_page("crm")
def print_crm_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    items = []
    subtotal = float(quote.subtotal or 0)
    for it in quote.items:
        items.append({
            "description": it.description,
            "qty": it.qty,
            "unit_price": it.unit_price,
            "total": float(it.qty or 1) * float(it.unit_price or 0),
        })
    tax = subtotal * float(quote.tax_rate or 0) / 100
    return render_template(
        "print_crm_quote.html",
        quote=quote,
        items=items,
        subtotal=subtotal,
        tax=tax,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/crm-contract/<int:contract_id>")
@require_page("crm")
def print_crm_contract(contract_id):
    contract = CrmContract.query.get_or_404(contract_id)
    return render_template(
        "print_crm_contract.html",
        contract=contract,
        fmt=_fmt_date,
        money=_fmt_money,
    )


@pages_bp.route("/documents/crm-quote/<int:quote_id>/pdf")
@require_page("crm")
def download_crm_quote_pdf(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return _pdf_response(build_crm_quote_pdf(quote, get_lang()),
                         f"quote-{quote.quote_number}.pdf")


@pages_bp.route("/documents/crm-contract/<int:contract_id>/pdf")
@require_page("crm")
def download_crm_contract_pdf(contract_id):
    contract = CrmContract.query.get_or_404(contract_id)
    return _pdf_response(build_crm_contract_pdf(contract, get_lang()),
                         f"contract-{contract.contract_number}.pdf")


@pages_bp.route("/reports/financial-year/<int:year_id>")
@require_page("financial_years")
def financial_year_report(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    invoices = Invoice.query.filter_by(financial_year_id=year.id).all()
    orders = PurchaseOrder.query.filter_by(financial_year_id=year.id).all()
    contracts = RentalContract.query.filter_by(financial_year_id=year.id).all()
    plans = PaymentPlan.query.filter_by(financial_year_id=year.id).all()

    total_sales = sum(float(i.amount or 0) for i in invoices if i.invoice_type == "sales")
    total_purchases = sum(float(i.amount or 0) for i in invoices if i.invoice_type == "purchase")
    total_invoices = total_sales + total_purchases
    total_orders = sum(float(o.total or 0) for o in orders)
    rental_monthly = sum(float(c.monthly_rent or 0) for c in contracts)
    plans_total = sum(float(p.total_amount or 0) for p in plans)
    plans_paid = sum(p.paid_total() for p in plans)
    plans_balance = plans_total - plans_paid

    cur_info = _base_currency_info(year)
    currency_code = (cur_info or {}).get("code")
    currency_symbol = (cur_info or {}).get("symbol")
    currency_name = (cur_info or {}).get("name")

    def moneyc(v):
        suffix = currency_symbol or currency_code
        return (_fmt_money(v) + (f" {suffix}" if suffix else ""))

    return render_template(
        "financial_year_report.html",
        year=year,
        company=year.company,
        invoices=invoices,
        orders=orders,
        contracts=contracts,
        plans=plans,
        total_sales=total_sales,
        total_purchases=total_purchases,
        total_invoices=total_invoices,
        total_orders=total_orders,
        rental_monthly=rental_monthly,
        plans_total=plans_total,
        plans_paid=plans_paid,
        plans_balance=plans_balance,
        currency_code=currency_code,
        currency_symbol=currency_symbol,
        currency_name=currency_name,
        today=datetime.date.today(),
        fmt=_fmt_date,
        money=_fmt_money,
        moneyc=moneyc,
    )
