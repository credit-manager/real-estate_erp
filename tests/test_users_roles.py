"""Users and roles module tests."""
import pytest
import os


@pytest.mark.auth
class TestUsers:
    """User management tests."""

    def test_list_users(self, auth_client):
        resp = auth_client.get("/api/users")
        assert resp.status_code == 200

    def test_create_user(self, auth_client):
        resp = auth_client.post("/api/users", json={
            "username": f"testuser-{os.urandom(4).hex()}",
            "password": "TestPass123!",
            "full_name": "مستخدم اختباري",
        })
        assert resp.status_code in (200, 201)

    def test_get_current_user(self, auth_client):
        resp = auth_client.get("/api/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        usernames = [u["username"] for u in data]
        assert "admin" in usernames


@pytest.mark.auth
class TestRoles:
    """Role management tests."""

    def test_list_roles(self, auth_client):
        resp = auth_client.get("/api/roles")
        assert resp.status_code == 200

    def test_create_role(self, auth_client):
        resp = auth_client.post("/api/roles", json={
            "name": f"دور اختبار-{os.urandom(3).hex()}",
            "permissions": {"dashboard": ["view"]},
        })
        assert resp.status_code in (200, 201)
