"""Regression coverage for ORM-level posting integrity guards."""
from datetime import date
from decimal import Decimal

import pytest


def _make_year(db, FinancialYear, company_id, *, closed=False, start=date(2026, 1, 1), end=date(2026, 12, 31)):
    year = FinancialYear(
        company_id=company_id,
        name=f"FY-{start.year}",
        start_date=start,
        end_date=end,
        is_active=not closed,
        is_closed=closed,
    )
    db.session.add(year)
    db.session.flush()
    return year


def test_posted_entry_rejects_closed_financial_year(app):
    from database import db
    from models import Account, Company, FinancialYear, JournalEntry, JournalEntryLine

    with app.app_context():
        company = Company(name="Integrity Test")
        db.session.add(company)
        db.session.flush()
        year = _make_year(db, FinancialYear, company.id, closed=True)
        a1 = Account(code="990001", name="Integrity A", type="asset")
        a2 = Account(code="990002", name="Integrity B", type="equity")
        db.session.add_all([a1, a2])
        db.session.flush()
        entry = JournalEntry(
            entry_number="TEST-CLOSED-001",
            date=date(2026, 2, 1),
            financial_year_id=year.id,
            status="posted",
        )
        entry.lines.extend([
            JournalEntryLine(account_id=a1.id, debit=Decimal("10.00"), credit=Decimal("0.00")),
            JournalEntryLine(account_id=a2.id, debit=Decimal("0.00"), credit=Decimal("10.00")),
        ])
        db.session.add(entry)
        with pytest.raises(ValueError, match="financialYearClosed"):
            db.session.commit()
        db.session.rollback()
        db.session.query(JournalEntry).filter_by(entry_number="TEST-CLOSED-001").delete(
            synchronize_session=False)
        for obj in (a1, a2, year, company):
            try:
                db.session.delete(db.session.merge(obj))
            except Exception:
                db.session.rollback()
        db.session.commit()


def test_posted_entry_rejects_unbalanced_lines(app):
    from database import db
    from models import Account, Company, FinancialYear, JournalEntry, JournalEntryLine

    with app.app_context():
        company = Company(name="Balance Test")
        db.session.add(company)
        db.session.flush()
        year = _make_year(db, FinancialYear, company.id)
        a1 = Account(code="990003", name="Balance A", type="asset")
        a2 = Account(code="990004", name="Balance B", type="equity")
        db.session.add_all([a1, a2])
        db.session.flush()
        entry = JournalEntry(
            entry_number="TEST-BAL-001",
            date=date(2026, 2, 1),
            financial_year_id=year.id,
            status="posted",
        )
        entry.lines.extend([
            JournalEntryLine(account_id=a1.id, debit=Decimal("10.00"), credit=Decimal("0.00")),
            JournalEntryLine(account_id=a2.id, debit=Decimal("0.00"), credit=Decimal("9.99")),
        ])
        db.session.add(entry)
        with pytest.raises(ValueError, match="notBalanced"):
            db.session.commit()
        db.session.rollback()
        db.session.query(JournalEntry).filter_by(entry_number="TEST-BAL-001").delete(
            synchronize_session=False)
        for obj in (a1, a2, year, company):
            try:
                db.session.delete(db.session.merge(obj))
            except Exception:
                db.session.rollback()
        db.session.commit()
