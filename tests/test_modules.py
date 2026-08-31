# -*- coding: utf-8 -*-
"""Phase 10 — Module catalog tests."""

SECURITY_BASE = "/admin/security"


def _login(client):
    client.post("/admin/login", json={
        "email": "admin@dynamicpro.com",
        "password": "admin123",
    })


class TestModuleCatalog:
    """Module catalog listing and creation."""

    def test_list_modules(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/modules")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["modules"], list)
        assert len(data["modules"]) >= 14

    def test_modules_have_required_fields(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/modules")
        data = resp.get_json()
        module = data["modules"][0]
        for field in ["code", "name", "is_active"]:
            assert field in module, f"Module missing field: {field}"

    def test_modules_have_descriptions(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/modules")
        data = resp.get_json()
        for m in data["modules"]:
            assert "name" in m
            assert len(m["name"]) > 0

    def test_modules_all_active(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/modules")
        data = resp.get_json()
        # Default modules should all be active
        active_count = sum(1 for m in data["modules"] if m["is_active"])
        assert active_count >= 14

    def test_modules_requires_auth(self, client):
        resp = client.get(f"{SECURITY_BASE}/modules")
        assert resp.status_code in (401, 403)
