"""Dashboard and utility tests."""
import pytest


@pytest.mark.smoke
class TestDashboard:
    """Dashboard stats tests."""

    def test_dashboard_stats(self, auth_client):
        resp = auth_client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "projects_count" in data
        assert "units_count" in data
        assert "customers_count" in data
        assert "total_revenue" in data
        assert "total_expenses" in data
        assert "revenue_trend" in data


@pytest.mark.smoke
class TestOpenAPI:
    """OpenAPI documentation tests."""

    def test_swagger_spec(self, client):
        resp = client.get("/api/docs/swagger.json")
        assert resp.status_code == 200
        spec = resp.get_json()
        assert spec["openapi"] == "3.0.3"
        assert "paths" in spec

    def test_redoc_ui(self, client):
        resp = client.get("/api/docs/redoc")
        assert resp.status_code == 200


@pytest.mark.smoke
class TestEInvoice:
    """E-invoice utility tests."""

    def test_einvoice_unified_builder(self, app):
        from utils.einvoice import build_unified
        from models import Invoice, InvoiceItem
        from datetime import date
        with app.app_context():
            inv = Invoice(invoice_number="EINV-T1", invoice_type="sales",
                          amount=1150, issue_date=date.today())
            inv.items = [InvoiceItem(description="وحدة سكنية", quantity=1,
                                     unit_price=1000, tax_rate=15)]
            u = build_unified(inv)
            assert u["totals"]["net_amount"] == 1000.0
            assert u["totals"]["vat_amount"] == 150.0
            assert u["totals"]["total_amount"] == 1150.0

    def test_einvoice_qr_tlv(self):
        from utils.einvoice import build_qr_payload
        import base64
        unified = {
            "seller": {"name": "شركة تجربة", "tax_number": "300012345600003"},
            "totals": {"total_amount": 1150.0, "vat_amount": 150.0},
        }
        b64 = build_qr_payload(unified)
        raw = base64.b64decode(b64)
        assert "شركة تجربة".encode() in raw

    def test_einvoice_countries_22(self):
        from utils.einvoice import COUNTRIES
        assert len(COUNTRIES) == 22
