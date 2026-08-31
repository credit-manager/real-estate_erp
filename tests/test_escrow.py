"""Escrow module tests — accounts, transactions."""
import pytest
import os


@pytest.mark.escrow
class TestEscrowAccounts:
    """Escrow account CRUD tests."""

    def test_create_escrow_account(self, auth_client, sample_project):
        resp = auth_client.post("/api/escrow/accounts", json={
            "project_id": sample_project["id"],
            "bank_name": "بنك الراجحي",
            "iban": f"SA1234567890{os.urandom(5).hex()}",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "escrow_number" in data
        assert data["bank_name"] == "بنك الراجحي"

    def test_list_escrow_accounts(self, auth_client):
        resp = auth_client.get("/api/escrow/accounts")
        assert resp.status_code == 200


@pytest.mark.escrow
class TestEscrowTransactions:
    """Escrow transaction tests — deposits, releases, insufficient balance."""

    def _create_account(self, auth_client, sample_project):
        resp = auth_client.post("/api/escrow/accounts", json={
            "project_id": sample_project["id"],
            "bank_name": "بنك الأهلي",
            "iban": f"SA9876543210{os.urandom(5).hex()}",
        })
        return resp.get_json()["id"]

    def test_deposit(self, auth_client, sample_project):
        acc_id = self._create_account(auth_client, sample_project)
        resp = auth_client.post(f"/api/escrow/accounts/{acc_id}/transactions", json={
            "amount": 50000,
            "type": "deposit",
            "description": "دفعة أولى",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type"] == "deposit"
        assert float(data["amount"]) == 50000

    def test_release(self, auth_client, sample_project):
        acc_id = self._create_account(auth_client, sample_project)
        # Deposit first
        auth_client.post(f"/api/escrow/accounts/{acc_id}/transactions", json={
            "amount": 50000, "type": "deposit", "description": "إيداع",
        })
        # Then release
        resp = auth_client.post(f"/api/escrow/accounts/{acc_id}/transactions", json={
            "amount": 10000, "type": "release", "description": "صرف للمقاول",
        })
        assert resp.status_code == 201
        assert resp.get_json()["type"] == "release"

    def test_insufficient_balance_rejected(self, auth_client, sample_project):
        acc_id = self._create_account(auth_client, sample_project)
        resp = auth_client.post(f"/api/escrow/accounts/{acc_id}/transactions", json={
            "amount": 10000, "type": "release", "description": "محاولة صرف بدون رصيد",
        })
        assert resp.status_code == 400
