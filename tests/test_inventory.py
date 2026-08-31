"""Inventory module tests — warehouses, items, stock."""
import pytest
import os


@pytest.mark.inventory
class TestWarehouses:
    """Warehouse tests."""

    def test_list_warehouses(self, auth_client):
        resp = auth_client.get("/api/inventory/warehouses")
        assert resp.status_code == 200

    def test_create_warehouse(self, auth_client):
        resp = auth_client.post("/api/inventory/warehouses", json={
            "name": f"مستودع اختبار-{os.urandom(3).hex()}",
            "code": f"WH-{os.urandom(4).hex().upper()}",
            "location": "الرياض",
        })
        assert resp.status_code in (200, 201)


@pytest.mark.inventory
class TestItems:
    """Item CRUD tests."""

    def test_list_items(self, auth_client):
        resp = auth_client.get("/api/inventory/items")
        assert resp.status_code == 200

    def test_create_item(self, auth_client):
        resp = auth_client.post("/api/inventory/items", json={
            "name": f"صنف اختبار-{os.urandom(3).hex()}",
            "code": f"ITM-{os.urandom(4).hex().upper()}",
            "cost_price": 100,
            "sale_price": 150,
        })
        assert resp.status_code in (200, 201)


@pytest.mark.inventory
class TestStock:
    """Stock management tests."""

    def test_list_stock(self, auth_client):
        resp = auth_client.get("/api/inventory/stock")
        assert resp.status_code == 200
