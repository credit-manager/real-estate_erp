# -*- coding: utf-8 -*-
"""Phase 10 — Security events, audit, analytics, and emergency controls tests."""

COMPANIES_URL = "/admin/companies"
SECURITY_BASE = "/admin/security"


def _login(client):
    client.post("/admin/login", json={
        "email": "admin@dynamicpro.com",
        "password": "admin123",
    })


class TestSecurityEvents:
    """Security event logging and retrieval."""

    def test_security_summary(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/security/summary")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "active_sessions" in data
        assert "login_success_24h" in data

    def test_security_events_list(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/security/events?limit=10")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["events"], list)

    def test_login_history(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/security/login-history?limit=5")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["events"], list)


class TestEmergencyControls:
    """Emergency security controls."""

    def test_kill_all_sessions_requires_permission(self, client):
        resp = client.post(f"{SECURITY_BASE}/security/kill-all-sessions")
        assert resp.status_code in (401, 403)

    def test_kill_all_sessions(self, client):
        _login(client)
        resp = client.post(f"{SECURITY_BASE}/security/kill-all-sessions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "revoked" in data


class TestAudit:
    """Audit log querying."""

    def test_audit_log(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/audit?limit=10")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["logs"], list)

    def test_audit_entries_have_required_fields(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/audit?limit=1")
        data = resp.get_json()
        if data["logs"]:
            log = data["logs"][0]
            for field in ["id", "action", "created_at", "result"]:
                assert field in log, f"Audit log missing field: {field}"


class TestAnalytics:
    """Analytics endpoints."""

    def test_platform_overview(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/analytics/overview")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "companies" in data
        assert "revenue" in data
        assert "modules" in data

    def test_company_analytics(self, client):
        _login(client)
        resp = client.get(COMPANIES_URL)
        companies = resp.get_json()["companies"]
        if not companies:
            return
        cid = companies[0]["id"]
        resp = client.get(f"{SECURITY_BASE}/analytics/companies/{cid}")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "company" in data

    def test_revenue_analytics(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/analytics/revenue")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "monthly" in data

    def test_module_adoption(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/analytics/modules")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["modules"], list)
        assert len(data["modules"]) > 0

    def test_subscription_summary(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/analytics/subscriptions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "statuses" in data
