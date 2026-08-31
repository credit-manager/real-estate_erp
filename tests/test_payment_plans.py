"""Payment plans and installments tests."""
import pytest


@pytest.mark.smoke
class TestPaymentPlans:
    """Payment plan and installment tests."""

    def test_aging_report(self, auth_client):
        resp = auth_client.get("/api/payment-plans/aging")
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("rows", "summary", "total_overdue", "overdue_count"):
            assert key in data
        for bar in ("0-30", "31-60", "61-90", "90+"):
            assert bar in data["summary"]

    def test_list_payment_plans(self, auth_client):
        resp = auth_client.get("/api/payment-plans")
        assert resp.status_code == 200
