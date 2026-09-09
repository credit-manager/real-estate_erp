# -*- coding: utf-8 -*-
"""Commercial accounting invariants for financial-year lifecycle."""
import uuid


def _company(app):
    from database import db
    from models import Company

    name = f"Test FY Company {uuid.uuid4().hex[:8]}"
    company = Company(name=name, email=f"{uuid.uuid4().hex[:8]}@example.test")
    db.session.add(company)
    db.session.commit()
    return company.id


def test_financial_year_rejects_inverted_dates(auth_client, app):
    with app.app_context():
        company_id = _company(app)
    response = auth_client.post("/api/financial-years", json={
        "company_id": company_id,
        "name": "Invalid",
        "start_date": "2026-12-31",
        "end_date": "2026-01-01",
    })
    assert response.status_code == 400
    assert response.get_json()["error_key"] == "financialYears.invalidDateRange"


def test_financial_year_rejects_overlap(auth_client, app):
    with app.app_context():
        company_id = _company(app)
    payload = {
        "company_id": company_id,
        "name": "2026",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
    }
    first = auth_client.post("/api/financial-years", json=payload)
    assert first.status_code == 201
    second = auth_client.post("/api/financial-years", json={**payload, "name": "2026 overlap"})
    assert second.status_code == 400
    assert second.get_json()["error_key"] == "financialYears.overlap"


def test_financial_year_delete_rejects_linked_transactions(auth_client, app):
    with app.app_context():
        company_id = _company(app)
    created = auth_client.post("/api/financial-years", json={
        "company_id": company_id,
        "name": "2027",
        "start_date": "2027-01-01",
        "end_date": "2027-12-31",
    })
    assert created.status_code == 201
    year_id = created.get_json()["year"]["id"]

    with app.app_context():
        from database import db
        from models import JournalEntry
        entry = JournalEntry(
            entry_number=f"FY-TEST-{uuid.uuid4().hex[:10]}",
            date=__import__("datetime").date(2027, 2, 1),
            financial_year_id=year_id,
            status="posted",
        )
        db.session.add(entry)
        db.session.commit()

    response = auth_client.delete(f"/api/financial-years/{year_id}")
    assert response.status_code == 409
    assert response.get_json()["error_key"] == "financialYears.hasTransactions"
