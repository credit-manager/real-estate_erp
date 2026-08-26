"""ينشئ ملف PDF من مصدر المشروع المباشر (لنافذة حفظ التطبيق).

الاستخدام:
    python live_pdf_builder.py <doc_type> <doc_id> <lang> <output_path>

يدعم: invoice | po | contract | financial-year
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main():
    if len(sys.argv) < 5:
        sys.exit(1)
    doc_type, doc_id, lang, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]

    from app import app
    from database import db
    from models import Invoice, PurchaseOrder, RentalContract, FinancialYear
    from utils.pdf import (
        build_invoice_pdf,
        build_po_pdf,
        build_contract_pdf,
        build_financial_year_report_pdf,
    )

    builders = {
        "invoice": (Invoice, build_invoice_pdf),
        "po": (PurchaseOrder, build_po_pdf),
        "contract": (RentalContract, build_contract_pdf),
        "financial-year": (FinancialYear, build_financial_year_report_pdf),
    }
    if doc_type not in builders:
        sys.exit(2)
    model, builder = builders[doc_type]

    with app.app_context():
        doc = db.session.get(model, doc_id)
        if doc is None:
            sys.exit(3)
        data = builder(doc, lang)

    with open(out, "wb") as fh:
        fh.write(data)
    print("OK")


if __name__ == "__main__":
    main()
