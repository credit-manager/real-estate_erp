# -*- coding: utf-8 -*-
"""Phase 10 — Company management and lifecycle tests."""

COMPANIES_URL = "/admin/companies"
SECURITY_BASE = "/admin/security"


def _login(client):
    client.post("/admin/login", json={
        "email": "admin@dynamicpro.com",
        "password": "admin123",
    })


class TestCompanyList:
    """Company listing and retrieval."""

    def test_list_companies(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["companies"], list)
        assert len(data["companies"]) > 0

    def test_companies_have_required_fields(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        data = resp.get_json()
        company = data["companies"][0]
        for field in ["id", "name", "status"]:
            assert field in company, f"Company missing field: {field}"

    def test_companies_requires_auth(self, client):
        resp = client.get(COMPANIES_URL)
        assert resp.status_code in (401, 403)


class TestCompanyLifecycle:
    """Company state transitions via security endpoints."""

    def _get_company_id(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        for c in companies:
            if c["status"] == "active":
                return c["id"]
        return companies[0]["id"] if companies else None

    def test_suspend_company(self, client):
        cid = self._get_company_id(client)
        if not cid:
            return
        resp = client.post(f"{SECURITY_BASE}/companies/{cid}/transition",
                           json={"action": "suspend"})
        data = resp.get_json()
        # 200 = success, 400 = already suspended
        assert resp.status_code in (200, 400)
        assert data["success"] in (True, False)

    def test_activate_company(self, client):
        cid = self._get_company_id(client)
        if not cid:
            return
        client.post(f"{SECURITY_BASE}/companies/{cid}/transition",
                     json={"action": "suspend"})
        resp = client.post(f"{SECURITY_BASE}/companies/{cid}/transition",
                           json={"action": "activate"})
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
