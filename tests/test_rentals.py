"""Rental module tests — contracts, renewals, payments."""
import pytest
import os
from datetime import date, timedelta


@pytest.mark.rentals
class TestRentalContracts:
    """Rental contract CRUD tests."""

    def test_create_rental_contract(self, auth_client, sample_unit, sample_customer):
        resp = auth_client.post("/api/rental-contracts", json={
            "unit_id": sample_unit["id"],
            "tenant_id": sample_customer["id"],
            "monthly_rent": 5000,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=365)).isoformat(),
        })
        assert resp.status_code in (200, 201)

    def test_list_rental_contracts(self, auth_client):
        resp = auth_client.get("/api/rental-contracts")
        assert resp.status_code == 200


@pytest.mark.rentals
class TestRentalPayments:
    """Rental payment tests."""

    def test_list_rental_payments(self, auth_client):
        resp = auth_client.get("/api/rentals/payments")
        assert resp.status_code == 200
