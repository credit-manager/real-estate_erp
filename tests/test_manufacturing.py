"""Manufacturing module tests — work centers, BOM, production orders."""
import pytest
import os


@pytest.mark.smoke
class TestManufacturing:
    """Manufacturing module tests."""

    def test_list_work_centers(self, auth_client):
        resp = auth_client.get("/api/mf/work-centers")
        assert resp.status_code == 200

    def test_list_bom(self, auth_client):
        resp = auth_client.get("/api/mf/boms")
        assert resp.status_code == 200

    def test_list_production_orders(self, auth_client):
        resp = auth_client.get("/api/mf/orders")
        assert resp.status_code == 200

    def test_list_raw_materials(self, auth_client):
        resp = auth_client.get("/api/mf/raw-materials")
        assert resp.status_code == 200
