# -*- coding: utf-8 -*-
"""Smoke test: analytics module computes KPIs + alerts against a seeded SQLite DB."""
from datetime import date, timedelta

from database import db
from models import (
    Customer, Invoice, InvoiceItem, Item, ItemStock, PurchaseOrder,
    Quote, RentalContract, Warehouse,
)
from utils.analytics import compute_analytics, compute_alerts


def test_analytics_and_alerts(app):
    with app.app_context():
        c = Customer(full_name="زبون تجريبي")
        db.session.add(c)
        db.session.flush()

        wh = Warehouse(code="WH", name="مخزن رئيسي")
        db.session.add(wh)
        db.session.flush()

        it = Item(code="ITM-1", name="خامة أ", reorder_level=5, cost_price=10, is_active=True)
        db.session.add(it)
        db.session.flush()
        db.session.add(ItemStock(item_id=it.id, warehouse_id=wh.id, quantity=2, avg_cost=10))

        today = date.today()
        inv = Invoice(
            invoice_number="INV-1", invoice_type="sales", amount=1000, paid_amount=400,
            customer_id=c.id, status="partial", issue_date=today - timedelta(days=90),
            due_date=today - timedelta(days=10),
        )
        db.session.add(inv)
        db.session.flush()
        db.session.add(InvoiceItem(invoice_id=inv.id, description="بند أ",
                                   quantity=2, unit_price=500, tax_rate=0))

        db.session.add(RentalContract(
            contract_number="RC-1", monthly_rent=1500, status="active",
            start_date=today, end_date=today + timedelta(days=10),
        ))
        db.session.add(PurchaseOrder(po_number="PO-1", status="pending"))
        db.session.add(Quote(quote_number="Q-1", status="sent",
                             valid_until=today - timedelta(days=2), subtotal=900))
        db.session.commit()

        a = compute_analytics()
        assert a["kpis"]["revenue"] == 1000.0
        assert a["kpis"]["revenue_paid"] == 400.0
        assert a["kpis"]["receivables_overdue"] == 600.0
        assert a["kpis"]["stock_value"] == 20.0
        assert a["kpis"]["low_stock_items"] >= 1
        assert a["aging"]["90_plus"] == 0
        assert a["aging"]["31_60"] == 0
        assert a["aging"]["0_30"] == 600.0
        assert len(a["trend"]) == 12
        assert a["top_products"][0]["name"] == "بند أ"
        assert a["top_customers"][0]["name"] == "زبون تجريبي"

        al = compute_alerts()
        types = {x["type"] for x in al["alerts"]}
        assert "low_stock" in types
        assert "overdue_invoice" in types
        assert "contract_expiring" in types
        assert "pending_po" in types
        assert "expired_quotes" in types
        assert al["summary"]["critical"] >= 1
        assert al["summary"]["info"] >= 1