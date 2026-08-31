"""CRM module tests — leads, opportunities, campaigns."""
import pytest
import os


@pytest.mark.crm
class TestLeads:
    """Lead CRUD tests."""

    def test_create_lead(self, auth_client):
        resp = auth_client.post("/api/crm/leads", json={
            "full_name": f"عميل محتمل-{os.urandom(3).hex()}",
            "phone": "0501234567",
            "source": "website",
        })
        assert resp.status_code in (200, 201)

    def test_list_leads(self, auth_client):
        resp = auth_client.get("/api/crm/leads")
        assert resp.status_code == 200


@pytest.mark.crm
class TestOpportunities:
    """Opportunity tests."""

    def test_list_opportunities(self, auth_client):
        resp = auth_client.get("/api/crm/opportunities")
        assert resp.status_code == 200


@pytest.mark.crm
class TestCampaigns:
    """Campaign tests."""

    def test_list_campaigns(self, auth_client):
        resp = auth_client.get("/api/crm/campaigns")
        assert resp.status_code == 200


@pytest.mark.crm
class TestSupportTickets:
    """Support ticket tests."""

    def test_list_tickets(self, auth_client):
        resp = auth_client.get("/api/crm/tickets")
        assert resp.status_code == 200
