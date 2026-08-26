"""Server-side PDF generation for printable documents (fpdf2)."""
import os
from datetime import date

from fpdf import FPDF

from database import db
from i18n import make_t
import utils.settings as settings_module

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\DUBAI-REGULAR.TTF", r"C:\Windows\Fonts\DUBAI-BOLD.TTF"),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
]

FONT_AR = None
FONT_AR_BOLD = None
for _reg, _bold in _FONT_CANDIDATES:
    if os.path.exists(_reg):
        FONT_AR = _reg
        FONT_AR_BOLD = _bold if os.path.exists(_bold) else _reg
        break
if FONT_AR is None:
    FONT_AR = "helvetica"
    FONT_AR_BOLD = "helvetica"

_INK = (30, 32, 37)
_MUT = (104, 110, 121)
_ACC = (96, 103, 84)
_HEAD_BG = (240, 241, 236)
_LINE = (216, 219, 226)
_TOTAL_BG = (248, 248, 246)
_GRAND_BG = (235, 236, 229)


def _fmt_money(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        f = 0
    dec = settings_module.get_int("number_decimals", 2)
    return f"{f:,.{dec}f}"


def _fmt_date(d):
    fmt = settings_module.get("date_format", "dd/mm/yyyy")
    if not d:
        return "—"
    return d.strftime("%Y-%m-%d") if fmt == "yyyy-mm-dd" else d.strftime("%d/%m/%Y")


def _doc_footer(t):
    """سطر التذييل القياسي للمستندات: تذييل مخصص + اسم النظام + تاريخ الإنشاء."""
    sysname = settings_module.get("system_name", "Dynamic Pro ERP")
    footer = (settings_module.get("doc_footer_text", "") or "").strip()
    gen = t("doc.generated") + " " + _fmt_date(date.today())
    return (footer + " — " if footer else "") + sysname + " — " + gen


def _base_currency_info(doc):
    """يعيد معلومات العملة الأساسية لمستند أو سنة مالية أو شركة، مع الرجوع للعملة الافتراضية."""
    company = None
    if hasattr(doc, "financial_year") and doc.financial_year:
        company = doc.financial_year.company
    elif hasattr(doc, "company") and doc.company:
        company = doc.company
    elif hasattr(doc, "currencies") and doc.currencies:
        company = doc
    if company is not None:
        for c in company.currencies:
            if c.is_base:
                return {"code": c.code, "symbol": c.symbol, "name": c.name}
        code = company.currency
        if code:
            return {"code": code, "symbol": code, "name": code}
    cid = settings_module.get_int("default_currency_id", None)
    if cid:
        from models.currency import Currency
        cur = db.session.get(Currency, cid)
        if cur:
            return {"code": cur.code, "symbol": cur.symbol, "name": cur.name}
    return None


def _currency_suffix(doc):
    info = _base_currency_info(doc)
    if not info:
        return ""
    return info.get("symbol") or info.get("code") or ""


class DocPDF(FPDF):
    def __init__(self, lang="ar"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.lang = lang
        self.rtl = lang == "ar"
        self.footer_text = ""
        self.set_margins(15, 12, 15)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_text_shaping(True)
        self._family = "main"
        if FONT_AR == "helvetica":
            self._family = "helvetica"
        else:
            self.add_font("main", fname=FONT_AR)
            self.add_font("main", style="B", fname=FONT_AR_BOLD)
        self._font(10)

    def _font(self, size, style=""):
        self.set_font(self._family, style=style, size=size)

    def _ink(self, c):
        self.set_text_color(*c)

    def _line(self, y, color=None):
        self.set_draw_color(*(color or _LINE))
        self.line(15, y, 195, y)

    def _col_x(self, widths, i):
        if self.rtl:
            return 195 - sum(widths[: i + 1])
        return 15 + sum(widths[:i])

    def _brand(self, x, y, w):
        """يرسم شعار النظام أو اسمه في رأس المستند."""
        logo = (settings_module.get("system_logo", "") or "").strip()
        if logo:
            try:
                self.image(logo, x, y, 30, 12)
                return
            except Exception:
                pass
        self._font(16)
        self._ink(_INK)
        self.cell(w, 8, (settings_module.get("system_name", "Dynamic Pro ERP") or "Dynamic Pro ERP")[:18])

    def header_block(self, title, doc_no, subtitle):
        half = 90
        if self.rtl:
            self.set_xy(15, 14)
            self._font(9)
            self._ink(_MUT)
            self.multi_cell(half, 4.5, subtitle, align="L")
            self.set_xy(15, 26)
            self._brand(15, 26, half)
            self.set_xy(105, 14)
            self._font(22)
            self._ink(_INK)
            self.cell(half, 10, title, align="R")
            self.set_xy(105, 30)
            self._font(11)
            self._ink(_ACC)
            self.cell(half, 7, doc_no, align="R")
        else:
            self.set_xy(15, 14)
            self._font(22)
            self._ink(_INK)
            self.cell(half, 10, title)
            self.set_xy(15, 26)
            self._font(11)
            self._ink(_ACC)
            self.cell(half, 7, doc_no)
            self.set_xy(105, 14)
            self._brand(105, 14, half)
            self.set_xy(105, 23)
            self._font(9)
            self._ink(_MUT)
            self.multi_cell(half, 4.5, subtitle, align="R")
        self.set_y(42)
        self._line(self.get_y())
        self.set_y(self.get_y() + 8)

    def meta_block(self, pairs):
        pair_w = 90
        label_w = 34
        for i, (label, value) in enumerate(pairs):
            x = 105 if (self.rtl and i % 2 == 0) or (not self.rtl and i % 2 == 1) else 15
            y = self.get_y()
            if self.rtl:
                self.set_xy(x, y)
                self._font(10)
                self._ink(_INK)
                self.cell(pair_w - label_w, 5, value, align="R")
                self.set_xy(x + pair_w - label_w, y)
                self._font(7.5)
                self._ink(_MUT)
                self.cell(label_w, 5, label, align="R")
            else:
                self.set_xy(x, y)
                self._font(7.5)
                self._ink(_MUT)
                self.cell(label_w, 5, label)
                self.set_x(x + label_w)
                self._font(10)
                self._ink(_INK)
                self.cell(pair_w - label_w, 5, value)
            if i % 2 == 1:
                self.set_y(y + 7)
        self.set_y(self.get_y() + 3)

    def parties(self, first_title, first_lines, second_title, second_lines):
        w = 90
        self.set_y(self.get_y() + 2)
        boxes = [(first_title, first_lines), (second_title, second_lines)]
        y0 = self.get_y()
        box_h = 11 + 5 * (max(len(first_lines), len(second_lines)) - 1)
        for idx, (title, lines) in enumerate(boxes):
            x = 105 if (self.rtl == (idx == 0)) else 15
            self.set_xy(x, y0)
            self._font(7.5)
            self._ink(_ACC)
            self.cell(w, 5, title, align="R" if self.rtl else "L")
            self.set_xy(x, y0 + 5)
            self._font(11)
            self._ink(_INK)
            self.cell(w, 6, lines[0] if lines else "—", align="R" if self.rtl else "L")
            y = y0 + 11
            self._font(9)
            self._ink(_MUT)
            for extra in lines[1:]:
                self.set_xy(x, y)
                self.cell(w, 5, extra, align="R" if self.rtl else "L")
                y += 5
        self.set_y(y0 + box_h + 6)
        self.ln(4)

    def section_title(self, text):
        self.set_y(self.get_y() + 2)
        self._font(11)
        self._ink(_ACC)
        self.cell(0, 6, text, align="R" if self.rtl else "L")
        self.ln(3)

    def items_table(self, headers, rows, totals, col_widths, desc_col=0):
        self.set_fill_color(*_HEAD_BG)
        y = self.get_y()
        for i, h in enumerate(headers):
            self.set_xy(self._col_x(col_widths, i), y)
            self._font(8, "B" if i == desc_col else "")
            self._ink(_ACC if i == desc_col else _INK)
            align = "R" if (self.rtl and i == desc_col) else "L" if (not self.rtl and i == desc_col) else "C"
            self.cell(col_widths[i], 7, h, fill=True, align=align)
        self.set_y(y + 7)
        self._line(self.get_y())
        self.ln(2)

        for row in rows:
            desc = str(row[desc_col] or "")
            pad = 2
            line_h = 5
            self._font(9.5)
            desc_w = self.get_string_width(desc)
            avail = col_widths[desc_col] - 2 * pad - 2
            lines = 1 if desc_w <= avail else int(desc_w / avail) + 1
            row_h = max(7, lines * line_h + 2)
            y = self.get_y()
            self.set_xy(self._col_x(col_widths, desc_col), y)
            self._font(9.5)
            self._ink(_INK)
            self.multi_cell(col_widths[desc_col], line_h, desc or "", align="R" if self.rtl else "L", padding=pad)
            for j, val in enumerate(row):
                if j == desc_col:
                    continue
                cx = self._col_x(col_widths, j)
                self.set_xy(cx, y + max(0, (row_h - 5) / 2))
                self._font(9.5)
                self._ink(_INK)
                self.cell(col_widths[j], 5, str(val or ""), align="C")
            self.set_y(y + row_h)
            self._line(self.get_y())
            self.ln(1)

        grand_idx = len(totals) - 1
        for i, (label, value, emph) in enumerate(totals):
            y = self.get_y()
            label_w = sum(col_widths) - 62
            value_w = 62
            if self.rtl:
                label_x = 15 + value_w
                value_x = 15
            else:
                label_x = 15
                value_x = 15 + label_w
            self.set_fill_color(_GRAND_BG if i == grand_idx else _TOTAL_BG)
            self.set_xy(label_x, y)
            self._font(10, "B" if emph else "")
            self._ink(_INK)
            self.cell(label_w, 7, label, fill=True, align="R" if self.rtl else "L")
            self.set_xy(value_x, y)
            self._font(10, "B" if emph else "")
            self.cell(value_w, 7, value, fill=True, align="C")
            self.set_y(y + 7)

    def terms(self, label, text):
        self.set_y(self.get_y() + 3)
        self._font(9.5)
        self._ink(_INK)
        self.cell(0, 6, label, align="R" if self.rtl else "L")
        self.ln(1)
        self._font(8.5)
        self._ink(_MUT)
        self.set_x(15)
        self.multi_cell(0, 4.5, text, align="R" if self.rtl else "L")

    def signatures(self, left_label, right_label):
        y = self.get_y() + 14
        if y > 258:
            self.add_page()
            y = 40
        w = 80
        x1 = 105 if self.rtl else 15
        x2 = 15 if self.rtl else 105
        self._line(y, _LINE)
        self._font(9)
        self._ink(_MUT)
        self.set_xy(x1, y + 3)
        self.cell(w, 5, left_label, align="C")
        self.set_xy(x2, y + 3)
        self.cell(w, 5, right_label, align="C")

    def footer(self):
        if self.footer_text:
            self.set_y(-14)
            self._font(8)
            self._ink(_MUT)
            self.cell(0, 5, self.footer_text, align="C")


def _fmt_num(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        f = 0
    return f"{f:g}"


def _party_lines(t, phone=None, email=None, address=None):
    return [ln for ln in [
        (t("common.phone") + ": " + phone) if phone else None,
        email or None,
        address or None,
    ] if ln]


# ============ Invoice ============
def build_invoice_pdf(invoice, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("doc.invoiceTitle"), invoice.invoice_number, t("app.subtitle"))
    pdf.meta_block([
        (t("doc.issueDate"), _fmt_date(invoice.issue_date)),
        (t("doc.dueDate"), _fmt_date(invoice.due_date)),
        (t("doc.status"), t("status." + (invoice.status or "pending"))),
        (t("doc.type"), t("finance.salesLabel") if invoice.invoice_type == "sales" else t("finance.expensesLabel")),
        (t("doc.financialYear"), invoice.financial_year.name if invoice.financial_year else "—"),
    ])
    cur = _base_currency_info(invoice)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    party_title = t("doc.billTo") if invoice.invoice_type == "sales" else t("doc.supplier")
    if invoice.invoice_type == "sales" and invoice.customer:
        c = invoice.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    elif invoice.supplier:
        s = invoice.supplier
        party = [s.company_name] + _party_lines(t, s.phone, s.email, s.address)
    else:
        party = ["—"]
    pdf.parties(party_title, party, t("doc.issuedBy"), ["Dynamic Pro", t("doc.companyInfo")])

    headers = [t("doc.colNo"), t("doc.description"), t("doc.qty"),
               t("doc.price"), t("doc.tax"), t("doc.total")]
    widths = [12, 82, 15, 23, 17, 31]
    if invoice.items:
        pdf.section_title(t("invoice.itemsTitle"))
        rows = []
        subtotal = 0.0
        total_tax = 0.0
        for idx, it in enumerate(invoice.items, 1):
            line = float(it.quantity or 0) * float(it.unit_price or 0)
            tax = line * float(it.tax_rate or 0) / 100
            subtotal += line
            total_tax += tax
            rows.append([str(idx), it.description, _fmt_num(it.quantity),
                         _fmt_money(it.unit_price), _fmt_money(tax), _fmt_money(line + tax)])
        pdf.items_table(headers, rows, [
            (t("doc.subtotal"), _fmt_money(subtotal), False),
            (t("doc.totalTax"), _fmt_money(total_tax), False),
            (t("doc.grandTotal"), _fmt_money(invoice.amount), True),
            (t("common.paid"), _fmt_money(invoice.paid_amount), False),
            (t("common.balance"), _fmt_money(invoice.amount - (invoice.paid_amount or 0)), False),
        ], widths)
        pdf.terms(t("doc.terms"), t("doc.termsText"))
        pdf.signatures(t("doc.sellerSign"), t("doc.buyerSign"))
        return pdf.output()
    else:
        pdf.section_title(t("doc.description"))
        pdf.items_table(
            [t("doc.colNo"), t("doc.description"), t("common.amount"), t("common.paid"), t("common.balance")],
            [[1, invoice.description or t("doc.generalItem"), _fmt_money(invoice.amount),
              _fmt_money(invoice.paid_amount),
              _fmt_money(invoice.amount - (invoice.paid_amount or 0))]],
            [(t("doc.total"), _fmt_money(invoice.amount), False)],
            [12, 78, 30, 30, 30],
            desc_col=1,
        )
        pdf.terms(t("doc.terms"), t("doc.termsText"))
        pdf.signatures(t("doc.sellerSign"), t("doc.buyerSign"))
        return pdf.output()


# ============ Purchase Order ============
def build_po_pdf(po, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("po.printTitle"), po.po_number, t("app.subtitle"))
    pdf.meta_block([
        (t("po.orderDate"), _fmt_date(po.order_date)),
        (t("po.deliveryDate"), _fmt_date(po.delivery_date)),
        (t("doc.status"), t("status." + (po.status or "pending"))),
        (t("po.projectLabel"), po.project.name if po.project else "—"),
        (t("doc.financialYear"), po.financial_year.name if po.financial_year else "—"),
    ])
    cur = _base_currency_info(po)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if po.supplier:
        s = po.supplier
        party = [s.company_name] + _party_lines(t, s.phone, s.email, s.address)
    else:
        party = ["—"]
    pdf.parties(t("po.supplierLabel"), party, t("doc.issuedBy"), ["Dynamic Pro", t("doc.companyInfo")])

    headers = [t("doc.colNo"), t("doc.description"), t("doc.qty"),
               t("doc.price"), t("doc.tax"), t("doc.total")]
    widths = [12, 82, 15, 23, 17, 31]
    if po.items:
        pdf.section_title(t("procurement.itemsTitle"))
        rows = []
        subtotal = 0.0
        total_tax = 0.0
        for idx, it in enumerate(po.items, 1):
            line = float(it.quantity or 0) * float(it.unit_price or 0)
            tax = line * float(it.tax_rate or 0) / 100
            subtotal += line
            total_tax += tax
            rows.append([str(idx), it.description, _fmt_num(it.quantity),
                         _fmt_money(it.unit_price), _fmt_money(tax), _fmt_money(line + tax)])
        pdf.items_table(headers, rows, [
            (t("doc.subtotal"), _fmt_money(subtotal), False),
            (t("doc.totalTax"), _fmt_money(total_tax), False),
            (t("doc.grandTotal"), _fmt_money(po.total), True),
        ], widths)
    else:
        pdf.section_title(t("common.description"))
        pdf.items_table(
            [t("doc.colNo"), t("doc.description"), t("common.total")],
            [[1, po.items_description or t("doc.generalItem"), _fmt_money(po.total)]],
            [(t("doc.total"), _fmt_money(po.total), False)],
            [12, 108, 60],
            desc_col=1,
        )
    if po.items_description:
        pdf.terms(t("common.description"), po.items_description)
    pdf.signatures(t("po.approvedBy"), t("po.supplierSign"))
    return pdf.output()


# ============ Sales Order ============
def build_sales_order_pdf(order, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("sales.printOrder"), order.order_number, t("app.subtitle"))
    pdf.meta_block([
        (t("doc.issueDate"), _fmt_date(order.order_date)),
        (t("doc.dueDate"), _fmt_date(order.due_date)),
        (t("doc.status"), t("status." + (order.status or "draft"))),
        (t("sales.salesperson"), order.salesperson.full_name if order.salesperson else "—"),
        (t("doc.financialYear"), order.financial_year.name if order.financial_year else "—"),
    ])
    cur = _base_currency_info(order)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if order.customer:
        c = order.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    else:
        party = ["—"]
    pdf.parties(t("doc.billTo"), party, t("doc.issuedBy"), ["Dynamic Pro", t("doc.companyInfo")])

    headers = [t("doc.colNo"), t("doc.description"), t("doc.qty"),
               t("doc.price"), t("doc.tax"), t("doc.total")]
    widths = [12, 82, 15, 23, 17, 31]
    if order.items:
        pdf.section_title(t("sales.orderItems"))
        rows = []
        subtotal = 0.0
        total_tax = 0.0
        for idx, it in enumerate(order.items, 1):
            line = float(it.quantity or 0) * float(it.unit_price or 0)
            tax = line * float(it.tax_rate or 0) / 100
            subtotal += line
            total_tax += tax
            rows.append([str(idx), it.description, _fmt_num(it.quantity),
                         _fmt_money(it.unit_price), _fmt_money(tax), _fmt_money(line + tax)])
        pdf.items_table(headers, rows, [
            (t("doc.subtotal"), _fmt_money(subtotal), False),
            (t("doc.totalTax"), _fmt_money(total_tax), False),
            (t("doc.grandTotal"), _fmt_money(order.amount), True),
            (t("common.paid"), _fmt_money(order.paid_amount), False),
            (t("common.balance"), _fmt_money(order.amount - (order.paid_amount or 0)), False),
        ], widths)
    else:
        pdf.section_title(t("doc.description"))
        pdf.items_table(
            [t("doc.colNo"), t("doc.description"), t("common.amount"), t("common.paid"), t("common.balance")],
            [[1, order.notes or t("doc.generalItem"), _fmt_money(order.amount),
              _fmt_money(order.paid_amount),
              _fmt_money(order.amount - (order.paid_amount or 0))]],
            [(t("doc.total"), _fmt_money(order.amount), False)],
            [12, 78, 30, 30, 30],
            desc_col=1,
        )
    if order.notes:
        pdf.terms(t("doc.notes"), order.notes)
    pdf.terms(t("doc.terms"), t("doc.termsText"))
    pdf.signatures(t("sales.sellerSign"), t("sales.buyerSign"))
    return pdf.output()


# ============ Sales Return ============
def build_sales_return_pdf(ret, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("sales.printReturn"), ret.return_number, t("app.subtitle"))
    pdf.meta_block([
        (t("sales.returnDate"), _fmt_date(ret.return_date)),
        (t("doc.status"), t("status." + (ret.status or "draft"))),
        (t("sales.returnInvoice"), ret.invoice.invoice_number if ret.invoice else "—"),
        (t("doc.financialYear"), ret.financial_year.name if ret.financial_year else "—"),
    ])
    cur = _base_currency_info(ret)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if ret.customer:
        c = ret.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    else:
        party = ["—"]
    pdf.parties(t("doc.billTo"), party, t("doc.issuedBy"), ["Dynamic Pro", t("doc.companyInfo")])

    headers = [t("doc.colNo"), t("doc.description"), t("doc.qty"),
               t("doc.price"), t("doc.tax"), t("doc.total")]
    widths = [12, 82, 15, 23, 17, 31]
    if ret.items:
        pdf.section_title(t("sales.returnItems"))
        rows = []
        subtotal = 0.0
        total_tax = 0.0
        for idx, it in enumerate(ret.items, 1):
            line = float(it.quantity or 0) * float(it.unit_price or 0)
            tax = line * float(it.tax_rate or 0) / 100
            subtotal += line
            total_tax += tax
            rows.append([str(idx), it.description, _fmt_num(it.quantity),
                         _fmt_money(it.unit_price), _fmt_money(tax), _fmt_money(line + tax)])
        pdf.items_table(headers, rows, [
            (t("doc.subtotal"), _fmt_money(subtotal), False),
            (t("doc.totalTax"), _fmt_money(total_tax), False),
            (t("doc.grandTotal"), _fmt_money(ret.amount), True),
        ], widths)
    else:
        pdf.section_title(t("doc.description"))
        pdf.items_table(
            [t("doc.colNo"), t("doc.description"), t("common.amount")],
            [[1, ret.reason or t("doc.generalItem"), _fmt_money(ret.amount)]],
            [(t("doc.total"), _fmt_money(ret.amount), False)],
            [12, 108, 60],
            desc_col=1,
        )
    if ret.reason:
        pdf.terms(t("sales.returnReason"), ret.reason)
    pdf.terms(t("doc.terms"), t("doc.termsText"))
    pdf.signatures(t("doc.firstPartySign"), t("doc.secondPartySign"))
    return pdf.output()


def _fmt_period(start, end):
    return _fmt_date(start) + " - " + _fmt_date(end) if start and end else "—"


# ============ Rental Contract ============
def build_contract_pdf(contract, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("doc.contractTitle"), contract.contract_number, t("app.subtitle"))
    pdf.meta_block([
        (t("doc.contractStatus"), t("status." + (contract.status or "active"))),
        (t("doc.startDate"), _fmt_date(contract.start_date)),
        (t("doc.endDate"), _fmt_date(contract.end_date)),
        (t("doc.monthlyRent"), _fmt_money(contract.monthly_rent)),
        (t("doc.financialYear"), contract.financial_year.name if contract.financial_year else "—"),
    ])
    cur = _base_currency_info(contract)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if contract.customer:
        c = contract.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    else:
        party = ["—"]
    pdf.parties(t("doc.firstParty"), ["Dynamic Pro", t("doc.companyInfo")],
                t("doc.secondParty"), party)

    unit = contract.unit
    if unit:
        pdf.section_title(t("doc.unit"))
        pdf.items_table(
            [t("doc.unit"), t("doc.unitType"), t("doc.area"), t("doc.floor"), t("doc.project")],
            [[unit.unit_code, unit.unit_type or "—",
              (f"{unit.area} " + t("doc.areaUnit")) if unit.area else "—",
              unit.floor or "—",
              unit.project.name if unit.project else "—"]],
            [],
            [30, 40, 40, 30, 40],
        )
    pdf.section_title(t("doc.terms"))
    for clause in [t("doc.clause1"), t("doc.clause2"), t("doc.clause3"), t("doc.clause4")]:
        pdf._font(9.5)
        pdf._ink(_INK)
        pdf.set_x(15)
        pdf.multi_cell(0, 5, "•  " + clause, align="R" if lang == "ar" else "L")
    pdf.signatures(t("doc.firstPartySign"), t("doc.secondPartySign"))
    return pdf.output()


# ============ CRM Quote ============
def build_crm_quote_pdf(quote, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("doc.quoteTitle"), quote.quote_number, t("app.subtitle"))
    pdf.meta_block([
        (t("doc.issueDate"), _fmt_date(quote.created_at.date() if quote.created_at else None)),
        (t("doc.validUntil"), _fmt_date(quote.valid_until)),
        (t("doc.status"), t("status." + (quote.status or "draft"))),
        (t("doc.customer"), quote.customer.full_name if quote.customer else "—"),
    ])
    cur = _base_currency_info(quote)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if quote.customer:
        c = quote.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    else:
        party = ["—"]
    pdf.parties(t("doc.customer"), party, t("doc.issuedBy"), ["Dynamic Pro", t("doc.companyInfo")])

    headers = [t("doc.colNo"), t("doc.description"), t("doc.qty"), t("doc.price"), t("doc.total")]
    widths = [12, 82, 18, 33, 35]
    rows = []
    for idx, it in enumerate(quote.items, 1):
        rows.append([str(idx), it.description, _fmt_num(it.qty),
                     _fmt_money(it.unit_price),
                     _fmt_money(float(it.qty or 1) * float(it.unit_price or 0))])
    tax = float(quote.subtotal or 0) * float(quote.tax_rate or 0) / 100
    pdf.section_title(t("doc.quoteItems"))
    pdf.items_table(headers, rows, [
        (t("doc.subtotal"), _fmt_money(quote.subtotal), False),
        (t("doc.discount"), _fmt_money(quote.discount), False),
        (t("doc.totalTax"), _fmt_money(tax), False),
        (t("doc.grandTotal"), _fmt_money(quote.total()), True),
    ], widths)
    if quote.notes:
        pdf.terms(t("doc.notes"), quote.notes)
    pdf.signatures(t("doc.sellerSign"), t("doc.buyerSign"))
    return pdf.output()


# ============ CRM Contract ============
def build_crm_contract_pdf(contract, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("doc.contract"), contract.contract_number, t("app.subtitle"))
    pdf.meta_block([
        (t("doc.status"), t("status." + (contract.status or "draft"))),
        (t("doc.startDate"), _fmt_date(contract.start_date)),
        (t("doc.endDate"), _fmt_date(contract.end_date)),
        (t("doc.contractValue"), _fmt_money(contract.value)),
    ])
    cur = _base_currency_info(contract)
    if cur:
        pdf.meta_block([
            (t("doc.currency"), (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") + f'{cur["name"]} ({cur["code"]})'),
        ])
    if contract.customer:
        c = contract.customer
        party = [c.full_name] + _party_lines(t, c.phone, c.email, c.address)
    else:
        party = ["—"]
    pdf.parties(t("doc.firstParty"), ["Dynamic Pro", t("doc.companyInfo")],
                t("doc.secondParty"), party)

    pdf.section_title(t("doc.contractDetails"))
    if contract.title:
        pdf._font(9.5)
        pdf._ink(_INK)
        pdf.set_x(15)
        pdf.multi_cell(0, 5, contract.title, align="R" if lang == "ar" else "L")
    if contract.quote:
        pdf._font(9)
        pdf._ink(_MUT)
        pdf.set_x(15)
        pdf.multi_cell(0, 5, t("doc.quoteNo") + ": " + contract.quote.quote_number, align="R" if lang == "ar" else "L")
    if contract.notes:
        pdf.terms(t("doc.notes"), contract.notes)
    pdf.signatures(t("doc.firstPartySign"), t("doc.secondPartySign"))
    return pdf.output()


def build_financial_year_report_pdf(year, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("fyReport.title"), year.name, t("app.subtitle"))
    cur = _base_currency_info(year)
    cur_suffix = (cur.get("symbol") or cur.get("code") or "") if cur else ""
    meta = [
        (t("fyReport.company"), year.company.name if year.company else "—"),
        (t("fyReport.period"), _fmt_period(year.start_date, year.end_date)),
        (t("fyReport.status"), t("financialYears." + ("active" if year.is_active else "closed"))),
    ]
    if cur:
        meta.append((t("doc.currency"),
                     (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") +
                     f'{cur["name"]} ({cur["code"]})'))
    pdf.meta_block(meta)

    def m(v):
        return (_fmt_money(v) + (" " + cur_suffix if cur_suffix else ""))

    headers = [t("fyReport.colUnit"), t("fyReport.colCustomer"), t("fyReport.colMonthly")]
    rows = []
    for c in year.rental_contracts:
        customer = c.customer.full_name if c.customer else "—"
        rows.append([c.contract_number, customer, m(c.monthly_rent)])
    if rows:
        pdf.section_title(t("fyReport.rentalContracts"))
        pdf.items_table(headers, rows, [], [20, 70, 40])

    headers = [t("fyReport.colUnit"), t("fyReport.colCustomer"), t("fyReport.colTotal")]
    rows = []
    for i in year.invoices:
        if i.invoice_type == "sales":
            customer = i.customer.full_name if i.customer else "—"
        else:
            customer = i.supplier.company_name if i.supplier else "—"
        rows.append([i.invoice_number, customer, m(i.amount)])
    if rows:
        pdf.section_title(t("fyReport.invoices"))
        pdf.items_table(headers, rows, [], [15, 65, 45])

    headers = [t("fyReport.colNo"), t("fyReport.colUnit"), t("fyReport.colTotal")]
    rows = []
    for p in year.purchase_orders:
        unit = p.project.name if p.project else "—"
        rows.append([p.po_number, unit, m(p.total)])
    if rows:
        pdf.section_title(t("fyReport.purchaseOrders"))
        pdf.items_table(headers, rows, [], [15, 65, 45])

    headers = [t("fyReport.colUnit"), t("fyReport.colCustomer"), t("fyReport.colDown"), t("fyReport.colMonths"), t("fyReport.colPaid"), t("fyReport.colBalance"), t("fyReport.colInstallments")]
    rows = []
    for pl in year.payment_plans:
        paid_inst = len([i for i in pl.installments if i.status == "paid"])
        rows.append([
            pl.unit.unit_code if pl.unit else str(pl.id),
            pl.customer.full_name if pl.customer else "—",
            m(pl.down_payment),
            str(pl.months),
            m(pl.paid_total()),
            m(float(pl.total_amount or 0) - pl.paid_total()),
            f"{paid_inst}/{len(pl.installments)}",
        ])
    if rows:
        pdf.section_title(t("fyReport.paymentPlans"))
        pdf.items_table(headers, rows, [], [20, 45, 25, 20, 25, 25, 20])

    total_sales = sum(float(i.amount or 0) for i in year.invoices if i.invoice_type == "sales")
    total_purchases = sum(float(i.amount or 0) for i in year.invoices if i.invoice_type == "purchase")
    total_orders = sum(float(o.total or 0) for o in year.purchase_orders)
    rental_monthly = sum(float(c.monthly_rent or 0) for c in year.rental_contracts)
    plans_total = sum(float(p.total_amount or 0) for p in year.payment_plans)
    plans_paid = sum(p.paid_total() for p in year.payment_plans)
    plans_balance = plans_total - plans_paid

    pdf.section_title(t("fyReport.title"))
    pdf.items_table([], [], [
        (t("fyReport.totalSales"), m(total_sales), False),
        (t("fyReport.totalPurchases"), m(total_purchases), False),
        (t("fyReport.totalInvoices"), m(total_sales + total_purchases), False),
        (t("fyReport.totalOrders"), m(total_orders), False),
        (t("fyReport.contractsMonthly"), m(rental_monthly), False),
        (t("fyReport.plansPaid"), m(plans_paid), False),
        (t("fyReport.plansBalance"), m(plans_balance), True),
    ], [180])

    pdf.signatures(t("doc.firstPartySign"), t("doc.secondPartySign"))
    return pdf.output()


def build_tax_report_pdf(report, lang):
    t = make_t(lang)
    pdf = DocPDF(lang)
    pdf.footer_text = _doc_footer(t)
    pdf.add_page()
    pdf.header_block(t("taxes.pdfTitle"), t("taxes.title"), t("app.subtitle"))

    cur = report.get("currency") or {}
    cur_suffix = (cur.get("symbol") or cur.get("code") or "") if cur else ""
    period = report.get("period") or {}
    meta = [
        (t("fyReport.company"), report.get("company_name") or "—"),
        (t("taxes.period"), _fmt_period(_iso_date(period.get("start")), _iso_date(period.get("end")))),
    ]
    if cur:
        meta.append((t("doc.currency"),
                     (cur["symbol"] + " " if cur.get("symbol") and cur["symbol"] != cur["code"] else "") +
                     f'{cur["name"]} ({cur["code"]})'))
    if report.get("company_tax_number"):
        meta.append((t("taxes.taxNumber"), report.get("company_tax_number")))
    pdf.meta_block(meta)

    def m(v):
        return (_fmt_money(v) + (" " + cur_suffix if cur_suffix else ""))

    net = float(report.get("net_tax") or 0)
    pdf.section_title(t("taxes.summary"))
    pdf.items_table([], [], [
        (t("taxes.outputTax"), m(report.get("output_tax") or 0), False),
        (t("taxes.inputTax"), m(report.get("input_tax") or 0), False),
        (t("taxes.netTax") + (" (" + t("taxes.refundable") + ")" if net < 0 else ""),
         m(abs(net)), True),
    ], [180])

    breakdown = report.get("breakdown") or []
    if breakdown:
        pdf.section_title(t("taxes.byRate"))
        rows = []
        for b in breakdown:
            rows.append([
                f"{_fmt_num(b['rate'])}%", m(b["output_base"]), m(b["output_tax"]),
                m(b["input_base"]), m(b["input_tax"]), m(b["net"]),
            ])
        pdf.items_table(
            [t("taxes.rateCol"), t("taxes.outputBase"), t("taxes.outputTax"),
             t("taxes.inputBase"), t("taxes.inputTax"), t("taxes.netCol")],
            rows, [], [18, 32, 32, 32, 32, 34],
        )

    docs = report.get("documents") or []
    if docs:
        pdf.section_title(t("taxes.docs"))
        rows = []
        for d in docs:
            kind = t("taxes.typeSales") if d["kind"] == "sales" else (
                t("taxes.typePurchase") if d["kind"] == "purchase" else (
                    t("taxes.typeExpense") if d["kind"] == "expense" else t("taxes.typePO")))
            rates = " / ".join(f"{_fmt_num(r)}%" for r in d.get("rates") or []) or "0%"
            rows.append([kind, d["number"], _fmt_date(_iso_date(d.get("date"))), d.get("party") or "—",
                         m(d["base"]), m(d["tax"]), rates])
        pdf.items_table(
            [t("taxes.docType"), t("taxes.docNumber"), t("taxes.docDate"), t("taxes.party"),
             t("taxes.taxBase"), t("taxes.taxAmount"), t("taxes.rateCol")],
            rows, [], [28, 30, 24, 48, 22, 22, 16],
            desc_col=3,
        )

    pdf.signatures(t("doc.firstPartySign"), t("doc.secondPartySign"))
    return pdf.output()


def _iso_date(value):
    if not value:
        return None
    try:
        from datetime import date as _d
        return _d.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
