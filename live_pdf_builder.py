"""PDF generation helpers for the packaged desktop application.

The desktop build imports this module directly; it must never spawn Python.exe
or depend on source files outside the frozen bundle.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def build_pdf_bytes(doc_type, doc_id, lang="ar"):
    """Return the requested document PDF as bytes."""
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
        raise ValueError(f"Unsupported PDF document type: {doc_type}")

    model, builder = builders[doc_type]
    with app.app_context():
        doc = db.session.get(model, int(doc_id))
        if doc is None:
            raise ValueError(f"Document not found: {doc_type}/{doc_id}")
        return builder(doc, lang)


def main():
    if len(sys.argv) < 5:
        sys.exit(1)
    doc_type, doc_id, lang, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    data = build_pdf_bytes(doc_type, doc_id, lang)
    with open(out, "wb") as fh:
        fh.write(data)
    print("OK")


if __name__ == "__main__":
    main()
