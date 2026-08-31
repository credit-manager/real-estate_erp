"""Procurement module tests — purchase requests, RFQs, POs, receiving."""
import pytest
import os


@pytest.mark.procurement
class TestPurchaseRequests:
    """Purchase request tests."""

    def test_list_purchase_requests(self, auth_client):
        resp = auth_client.get("/api/procurement/purchase-requests")
        assert resp.status_code == 200

    def test_create_purchase_request(self, auth_client):
        resp = auth_client.post("/api/procurement/purchase-requests", json={
            "title": f"طلب شراء اختبار-{os.urandom(3).hex()}",
            "items": [
                {"description": "حاسوب محمول", "quantity": 5, "estimated_price": 3000},
            ],
        })
        assert resp.status_code in (200, 201)


@pytest.mark.procurement
class TestRFQ:
    """Request for Quotation tests."""

    def test_list_rfq(self, auth_client):
        resp = auth_client.get("/api/procurement/rfqs")
        assert resp.status_code == 200


@pytest.mark.procurement
class TestPurchaseOrders:
    """Purchase order tests."""

    def test_create_po(self, auth_client, sample_supplier):
        resp = auth_client.post("/api/purchase-orders", json={
            "po_number": f"PO-{os.urandom(5).hex().upper()}",
            "supplier_id": sample_supplier["id"],
            "total": 50000,
            "items": [
                {"description": "مادة خام", "quantity": 10, "unit_price": 5000},
            ],
        })
        assert resp.status_code in (200, 201)

    def test_list_pos(self, auth_client):
        resp = auth_client.get("/api/purchase-orders")
        assert resp.status_code == 200
