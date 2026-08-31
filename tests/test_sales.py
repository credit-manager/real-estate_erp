"""Sales module tests — orders, returns, commissions."""
import pytest


@pytest.mark.sales
class TestSalesOrders:
    """Sales order CRUD tests."""

    def test_create_sales_order(self, auth_client, sample_customer):
        resp = auth_client.post("/api/sales/orders", json={
            "customer_id": sample_customer["id"],
            "order_date": "2026-08-27",
            "items": [
                {"description": "وحدة سكنية", "quantity": 1, "unit_price": 500000},
            ],
        })
        assert resp.status_code in (200, 201)

    def test_list_sales_orders(self, auth_client):
        resp = auth_client.get("/api/sales/orders")
        assert resp.status_code == 200


@pytest.mark.sales
class TestSalesReturns:
    """Sales return tests."""

    def test_list_sales_returns(self, auth_client):
        resp = auth_client.get("/api/sales/returns")
        assert resp.status_code == 200


@pytest.mark.sales
class TestSalesCommissions:
    """Sales commission tests."""

    def test_list_commissions(self, auth_client):
        resp = auth_client.get("/api/sales/commissions")
        assert resp.status_code == 200
