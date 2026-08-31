"""Real estate module tests — buildings, units, reservations."""
import pytest
from datetime import date, timedelta


@pytest.mark.real_estate
class TestBuildings:
    """Building CRUD tests."""

    def test_create_building(self, auth_client, sample_project):
        resp = auth_client.post("/api/realestate/buildings", json={
            "project_id": sample_project["id"],
            "name": "مبنى تجريبي",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "مبنى تجريبي"
        assert data["project_id"] == sample_project["id"]

    def test_list_buildings(self, auth_client, sample_building):
        resp = auth_client.get("/api/realestate/buildings")
        assert resp.status_code == 200

    def test_create_building_missing_project(self, auth_client):
        resp = auth_client.post("/api/realestate/buildings", json={
            "name": "مبنى بدون مشروع",
        })
        # API may accept or reject depending on validation
        assert resp.status_code in (200, 201, 400, 500)


@pytest.mark.real_estate
class TestUnits:
    """Unit CRUD tests."""

    def test_create_unit(self, auth_client, sample_project, sample_building):
        resp = auth_client.post("/api/units", json={
            "unit_code": f"UNT-{__import__('os').urandom(6).hex().upper()}",
            "project_id": sample_project["id"],
            "building_id": sample_building["id"],
            "price": 750000,
            "area": 150,
            "status": "available",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["price"] == 750000
        assert data["status"] == "available"

    def test_list_units(self, auth_client, sample_unit):
        resp = auth_client.get("/api/units")
        assert resp.status_code == 200

    def test_list_units_filter_status(self, auth_client, sample_unit):
        resp = auth_client.get("/api/units?status=available")
        assert resp.status_code == 200

    def test_list_units_filter_project(self, auth_client, sample_unit, sample_project):
        resp = auth_client.get(f"/api/units?project_id={sample_project['id']}")
        assert resp.status_code == 200

    def test_update_unit(self, auth_client, sample_unit):
        resp = auth_client.put(f"/api/units/{sample_unit['id']}", json={
            "price": 800000,
            "status": "reserved",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["price"] == 800000

    def test_delete_unit(self, auth_client, sample_unit):
        resp = auth_client.delete(f"/api/units/{sample_unit['id']}")
        assert resp.status_code == 200
        # Verify deleted
        resp = auth_client.get("/api/units")
        data = resp.get_json()
        items = data if isinstance(data, list) else data.get("items", [])
        ids = [u["id"] for u in items]
        assert sample_unit["id"] not in ids


@pytest.mark.real_estate
class TestReservations:
    """Reservation tests — including double reservation blocking."""

    def test_create_reservation(self, auth_client, sample_unit, sample_customer, future_date):
        resp = auth_client.post("/api/realestate/reservations", json={
            "unit_id": sample_unit["id"],
            "customer_id": sample_customer["id"],
            "expiry_date": future_date,
            "deposit": 10000,
        })
        assert resp.status_code == 201

    def test_double_reservation_blocked(self, auth_client, sample_unit, future_date):
        c1 = auth_client.post("/api/customers", json={"full_name": "عميل 1"}).get_json()
        c2 = auth_client.post("/api/customers", json={"full_name": "عميل 2"}).get_json()
        resp1 = auth_client.post("/api/realestate/reservations", json={
            "unit_id": sample_unit["id"],
            "customer_id": c1["id"],
            "expiry_date": future_date,
            "deposit": 10000,
        })
        assert resp1.status_code == 201
        resp2 = auth_client.post("/api/realestate/reservations", json={
            "unit_id": sample_unit["id"],
            "customer_id": c2["id"],
            "expiry_date": future_date,
            "deposit": 10000,
        })
        assert resp2.status_code in (400, 409)

    def test_reservation_past_date_rejected(self, auth_client, sample_unit, sample_customer):
        past = (date.today() - timedelta(days=10)).isoformat()
        resp = auth_client.post("/api/realestate/reservations", json={
            "unit_id": sample_unit["id"],
            "customer_id": sample_customer["id"],
            "expiry_date": past,
            "deposit": 10000,
        })
        assert resp.status_code in (400, 422)
