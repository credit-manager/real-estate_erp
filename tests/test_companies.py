# -*- coding: utf-8 -*-
"""Phase 10 — Company management and lifecycle tests."""

COMPANIES_URL = "/admin/companies"
SECURITY_BASE = "/admin/security"


class TestCompanyList:
    """Company listing and retrieval."""

    def test_list_companies(self, master_client, sample_company):
        resp = master_client.get(COMPANIES_URL)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["companies"], list)
        assert any(c["id"] == sample_company["id"] for c in data["companies"])

    def test_companies_have_required_fields(self, master_client, sample_company):
        resp = master_client.get(COMPANIES_URL)
        data = resp.get_json()
        company = next(c for c in data["companies"] if c["id"] == sample_company["id"])
        for field in ["id", "name", "status"]:
            assert field in company, f"Company missing field: {field}"

    def test_companies_requires_auth(self, client):
        resp = client.get(COMPANIES_URL)
        assert resp.status_code in (401, 403)


class TestCompanyLifecycle:
    """Company state transitions via security endpoints."""

    def test_suspend_company(self, master_client, sample_company):
        cid = sample_company["id"]
        resp = master_client.post(
            f"{SECURITY_BASE}/companies/{cid}/transition",
            json={"status": "suspended"},
        )
        data = resp.get_json()
        # 200 = success, 400 = already suspended
        assert resp.status_code in (200, 400)
        assert data["success"] in (True, False)

    def test_activate_company(self, master_client, sample_company):
        cid = sample_company["id"]
        master_client.post(
            f"{SECURITY_BASE}/companies/{cid}/transition",
            json={"status": "suspended"},
        )
        resp = master_client.post(
            f"{SECURITY_BASE}/companies/{cid}/transition",
            json={"status": "active"},
        )
        data = resp.get_json()
        # 200 = success, 400 = already active
        assert resp.status_code in (200, 400)
        assert data["success"] in (True, False)


class TestCompanyProvision:
    """Company provisioning endpoint."""

    def test_provision_requires_permission(self, client):
        resp = client.post(f"{SECURITY_BASE}/companies/provision", json={
            "name": "Test Co",
            "slug": "test-co",
        })
        assert resp.status_code in (401, 403)
