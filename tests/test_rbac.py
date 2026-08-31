# -*- coding: utf-8 -*-
"""Phase 10 — RBAC permission and role tests."""

SECURITY_BASE = "/admin/security"


def _login(client):
    client.post("/admin/login", json={
        "email": "admin@dynamicpro.com",
        "password": "admin123",
    })


class TestPermissions:
    """Permission catalog and user permissions."""

    def test_list_permissions(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/permissions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert len(data["permissions"]) >= 30

    def test_permission_codes_have_dot_notation(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/permissions")
        data = resp.get_json()
        for p in data["permissions"]:
            code = p["code"]
            assert "." in code, f"Permission '{code}' missing dot notation"
            parts = code.split(".")
            assert len(parts) == 2, f"Permission '{code}' should have exactly one dot"

    def test_me_includes_role(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/me")
        data = resp.get_json()
        assert resp.status_code == 200
        assert "role" in data["user"]


class TestRoles:
    """Role management."""

    def test_list_roles(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/roles")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert len(data["roles"]) >= 4

    def test_roles_have_permissions(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/roles")
        data = resp.get_json()
        for role in data["roles"]:
            assert "permissions" in role
            assert isinstance(role["permissions"], list)

    def test_super_admin_has_all_permissions(self, client):
        _login(client)
        resp = client.get(f"{SECURITY_BASE}/roles")
        data = resp.get_json()
        super_admin = next((r for r in data["roles"] if r["name"] == "super_admin"), None)
        assert super_admin is not None
        assert len(super_admin["permissions"]) >= 30


class TestRBACEnforcement:
    """Endpoints enforce RBAC."""

    def test_plans_endpoint_requires_auth(self, client):
        resp = client.get(f"{SECURITY_BASE}/plans")
        assert resp.status_code in (401, 403)

    def test_modules_endpoint_requires_auth(self, client):
        resp = client.get(f"{SECURITY_BASE}/modules")
        assert resp.status_code in (401, 403)

    def test_audit_endpoint_requires_auth(self, client):
        resp = client.get(f"{SECURITY_BASE}/audit")
        assert resp.status_code in (401, 403)
