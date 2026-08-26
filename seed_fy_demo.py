# -*- coding: utf-8 -*-
"""Build a complete demo financial year (2026) with documents & reports.

Run: python seed_fy_demo.py
- Fixes corrupted Arabic names of existing demo companies/branches.
- Ensures an active/open 2026 financial year for the active company.
- Links existing seed documents to the year.
- Creates additional rental contracts, payment plans + installments.
"""
from datetime import date, timedelta
from database import db
from app import create_app
from models import (
    Company, Branch, FinancialYear, Invoice, PurchaseOrder,
    RentalContract, PaymentPlan, Installment, RealEstateUnit,
)

app = create_app()

COMPANY_FIXES = {
    2: ("شركة النخبة للمقاولات", {
        2: ("فرع المقر الرئيسي", "القاهرة"),
        3: ("فرع مدينة نصر", "6 أكتوبر"),
    }),
    3: ("مؤسسة البنيان للمقاولات", {
        4: ("فرع المنصورة", "المنصورة"),
    }),
    4: ("مجموعة أجيليتي العقارية", {}),
}


def fix_company_names():
    for cid, (cname, branches) in COMPANY_FIXES.items():
        c = db.session.get(Company, cid)
        if c:
            c.name = cname
        for bid, (bname, bcity) in branches.items():
            b = db.session.get(Branch, bid)
            if b:
                b.name = bname
                b.city = bcity
    db.session.commit()
    print("OK: fixed company/branch Arabic names")


def ensure_year(company):
    year = FinancialYear.query.filter_by(company_id=company.id, name="2026").first()
    if not year:
        year = FinancialYear(
            company_id=company.id,
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
            is_closed=False,
        )
        db.session.add(year)
        db.session.commit()
    year.start_date = date(2026, 1, 1)
    year.end_date = date(2026, 12, 31)
    year.is_active = True
    year.is_closed = False
    for other in FinancialYear.query.filter_by(company_id=company.id, is_active=True).all():
        if other.id != year.id:
            other.is_active = False
    db.session.commit()
    print(f"OK: financial year 2026 active+open (id={year.id}, company={company.id})")
    return year


def link_existing(year):
    n = 0
    for i in Invoice.query.all():
        if i.financial_year_id != year.id:
            i.financial_year_id = year.id
            n += 1
    for o in PurchaseOrder.query.all():
        if o.financial_year_id != year.id:
            o.financial_year_id = year.id
            n += 1
    for r in RentalContract.query.all():
        if r.financial_year_id != year.id:
            r.financial_year_id = year.id
            n += 1
    for p in PaymentPlan.query.all():
        if p.financial_year_id != year.id:
            p.financial_year_id = year.id
            n += 1
    db.session.commit()
    print(f"OK: linked {n} existing documents to year {year.id}")


def add_rental(unit_id, customer_id, monthly, status="active", start=None, end=None):
    year_id = FinancialYear.query.filter_by(company_id=2, name="2026").first().id
    existing = RentalContract.query.filter_by(unit_id=unit_id).first()
    if existing:
        existing.financial_year_id = year_id
        u = db.session.get(RealEstateUnit, unit_id)
        if u:
            u.status = "rented"
        db.session.commit()
        print(f"SKIP: rental for unit {unit_id} already exists (RC-{existing.id}) -> linked to year")
        return existing
    start = start or date(2026, 1, 15)
    end = end or date(2026, 12, 31)
    rc = RentalContract(
        contract_number=f"RC-2026-{RentalContract.query.count() + 100}",
        unit_id=unit_id,
        customer_id=customer_id,
        monthly_rent=monthly,
        status=status,
        start_date=start,
        end_date=end,
        financial_year_id=year_id,
    )
    db.session.add(rc)
    u = db.session.get(RealEstateUnit, unit_id)
    if u:
        u.status = "rented"
    db.session.commit()
    print(f"OK: created rental RC-{rc.id} unit={unit_id} monthly={monthly}")
    return rc


def add_plan(unit_id, customer_id, total, down, months, fy_id, paid_months=0):
    existing = PaymentPlan.query.filter_by(unit_id=unit_id).first()
    if existing:
        existing.financial_year_id = fy_id
        db.session.commit()
        print(f"SKIP: plan for unit {unit_id} already exists (id={existing.id}) -> linked to year")
        return existing
    monthly = round((float(total) - float(down)) / months, 2)
    plan = PaymentPlan(
        unit_id=unit_id,
        customer_id=customer_id,
        financial_year_id=fy_id,
        total_amount=total,
        down_payment=down,
        monthly_amount=monthly,
        start_date=date(2026, 2, 1),
        months=months,
        status="active",
    )
    db.session.add(plan)
    db.session.commit()
    for i in range(1, months + 1):
        due = date(2026, 2, 1) + timedelta(days=30 * (i - 1))
        st = "pending"
        paid_amt = 0.0
        paid_date = None
        if i <= paid_months:
            st = "paid"
            paid_amt = monthly
            paid_date = due
        elif i <= paid_months + 2:
            st = "partial"
            paid_amt = round(monthly / 2, 2)
        db.session.add(Installment(
            plan_id=plan.id,
            installment_number=i,
            amount=monthly,
            paid_amount=paid_amt,
            due_date=due,
            paid_date=paid_date,
            status=st,
        ))
    db.session.commit()
    print(f"OK: created plan id={plan.id} unit={unit_id} total={total} months={months} paidMonths={paid_months}")
    return plan


def main():
    with app.app_context():
        fix_company_names()
        company = Company.query.filter_by(is_active=True).first() or Company.query.first()
        if not company:
            print("ERROR: no company found")
            return
        year = ensure_year(company)
        link_existing(year)

        # additional rental contracts for the year
        add_rental(unit_id=10, customer_id=4, monthly=18000)   # A-102
        add_rental(unit_id=15, customer_id=1, monthly=15000)   # D-102 shop

        # payment plans for the year
        add_plan(unit_id=13, customer_id=2, total=10000000, down=4000000, months=24, fy_id=year.id, paid_months=6)
        add_plan(unit_id=16, customer_id=4, total=3200000, down=0, months=36, fy_id=year.id, paid_months=3)

        db.session.commit()

        # summary
        print("===== SUMMARY =====")
        invs = Invoice.query.filter_by(financial_year_id=year.id).count()
        orders = PurchaseOrder.query.filter_by(financial_year_id=year.id).count()
        contracts = RentalContract.query.filter_by(financial_year_id=year.id).count()
        plans = PaymentPlan.query.filter_by(financial_year_id=year.id).count()
        print(f"year={year.name} company={company.name}")
        print(f"invoices={invs} orders={orders} contracts={contracts} plans={plans}")
        print("DONE")


if __name__ == "__main__":
    main()
