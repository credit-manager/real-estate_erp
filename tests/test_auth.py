"""Authentication module tests."""
import pytest


@pytest.mark.auth
class TestLogin:
    """Login endpoint tests."""

    def test_login_success(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["user"]["username"] == "admin"

    def test_login_wrong_password(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["success"] is False

    def test_login_nonexistent_user(self, client):
        resp = client.post("/login", json={"username": "nonexistent", "password": "test"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/login", json={})
        assert resp.status_code in (400, 401)

    def test_login_empty_password(self, client):
        resp = client.post("/login", json={"username": "admin", "password": ""})
        assert resp.status_code == 401


@pytest.mark.auth
class TestLogout:
    """Logout endpoint tests."""

    def test_logout_success(self, auth_client):
        resp = auth_client.post("/logout")
        assert resp.status_code == 200

    def test_logout_unauthenticated(self, client):
        resp = client.post("/logout")
        assert resp.status_code in (200, 401)


@pytest.mark.auth
class TestSession:
    """Session management tests."""

    def test_session_persists_after_login(self, auth_client):
        resp = auth_client.get("/api/dashboard/stats")
        assert resp.status_code == 200

    def test_session_cleared_after_logout(self, auth_client):
        auth_client.post("/logout")
        resp = auth_client.get("/api/dashboard/stats")
        assert resp.status_code in (302, 401)
