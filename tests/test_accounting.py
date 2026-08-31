"""Accounting module tests — journal entries, cost centers, fixed assets."""
import pytest


@pytest.mark.accounting
class TestJournalEntries:
    """Journal entry tests."""

    def test_create_balanced_entry(self, auth_client):
        resp = auth_client.post("/accounting/api/journal", json={
            "date": "2026-01-15",
            "description": "قيود اختبار",
            "lines": [
                {"account_id": 1, "debit": 1000, "credit": 0},
                {"account_id": 2, "debit": 0, "credit": 1000},
            ],
        })
        assert resp.status_code in (200, 201)

    def test_unbalanced_entry_rejected(self, auth_client):
        resp = auth_client.post("/accounting/api/journal", json={
            "date": "2026-01-15",
            "description": "قيود غير متساوية",
            "lines": [
                {"account_id": 1, "debit": 1000, "credit": 0},
                {"account_id": 2, "debit": 0, "credit": 500},
            ],
        })
        assert resp.status_code in (400, 500)

    def test_list_journal_entries(self, auth_client):
        resp = auth_client.get("/accounting/api/journal")
        assert resp.status_code == 200


@pytest.mark.accounting
class TestCostCenters:
    """Cost center tests."""

    def test_create_cost_center(self, auth_client):
        resp = auth_client.post("/accounting/api/cost-centers", json={
            "name": "مركز تكلفة اختباري",
            "code": f"CC-{__import__('os').urandom(3).hex()}",
        })
        assert resp.status_code in (200, 201)

    def test_list_cost_centers(self, auth_client):
        resp = auth_client.get("/accounting/api/cost-centers")
        assert resp.status_code == 200


@pytest.mark.accounting
class TestChartOfAccounts:
    """Chart of accounts tests."""

    def test_list_accounts(self, auth_client):
        resp = auth_client.get("/accounting/api/accounts")
        assert resp.status_code == 200

    def test_create_account(self, auth_client):
        resp = auth_client.post("/accounting/api/accounts", json={
            "name": "حساب اختباري",
            "code": f"TST-{__import__('os').urandom(3).hex()}",
            "type": "asset",
        })
        assert resp.status_code in (200, 201)
