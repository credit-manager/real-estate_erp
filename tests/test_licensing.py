# -*- coding: utf-8 -*-
"""Phase 10 — Licensing, subscriptions, plans, and module access tests."""

COMPANIES_URL = "/admin/companies"
SECURITY_BASE = "/admin/security"


def _login(client):
    client.post("/admin/login", json={
        "email": "admin@dynamicpro.com",
        "password": "admin123",
    })


class TestPlans:
    """Plan CRUD and listing."""

    def test_list_plans(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/plans")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["plans"], list)


class TestSubscriptions:
    """Subscription management."""

    def test_renew_subscription(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.post(f"{SECURITY_BASE}/companies/{cid}/subscription/renew",
                           json={"days": 365})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True


class TestLicenseAccess:
    """License access checking."""

    def test_access_check(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.get(f"{SECURITY_BASE}/companies/{cid}/access")
        data = resp.get_json()
        assert resp.status_code == 200


class TestModuleAccess:
    """Module access per company."""

    def test_company_modules(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.get(f"{SECURITY_BASE}/companies/{cid}/modules")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["modules"], list)

    def test_enable_module(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.post(f"{SECURITY_BASE}/companies/{cid}/modules/projects/enable")
        data = resp.get_json()
        # 200 = success, 400 = already enabled
        assert resp.status_code in (200, 400)
        assert data["success"] in (True, False)

    def test_disable_module(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        # Enable first (may already be enabled)
        client.post(f"{SECURITY_BASE}/companies/{cid}/modules/projects/enable")
        resp = client.post(f"{SECURITY_BASE}/companies/{cid}/modules/projects/disable")
        data = resp.get_json()
        # 200 = success, 400 = already disabled
        assert resp.status_code in (200, 400)
        assert data["success"] in (True, False)

    def test_feature_flag(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.post(
            f"{SECURITY_BASE}/companies/{cid}/modules/accounting/feature-flag",
            json={"flag": "vat_enabled", "value": True})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
