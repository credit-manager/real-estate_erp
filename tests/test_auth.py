# -*- coding: utf-8 -*-
"""Phase 10 — Authentication tests (login, JWT, sessions, me)."""


class TestLogin:
    """Master admin login flow."""

    def test_login_success(self, client):
        resp = client.post("/admin/login", json={
            "email": "admin@dynamicpro.com",
            "password": "admin123",
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "user" in data
        assert data["user"]["email"] == "admin@dynamicpro.com"

    def test_login_wrong_password(self, client):
        resp = client.post("/admin/login", json={
            "email": "admin@dynamicpro.com",
            "password": "wrongpassword",
        })
        data = resp.get_json()
        assert data["success"] is False

    def test_login_nonexistent_user(self, client):
        resp = client.post("/admin/login", json={
            "email": "nonexistent@dynamicpro.com",
            "password": "admin123",
        })
        data = resp.get_json()
        assert data["success"] is False

    def test_login_missing_fields(self, client):
        resp = client.post("/admin/login", json={})
        data = resp.get_json()
        assert data["success"] is False


class TestJWT:
    """JWT token lifecycle (session-based in test client)."""

    def test_me_with_session(self, client):
        """Login via session, then call /me — tokens are in Flask session."""
        client.post("/admin/login", json={
            "email": "admin@dynamicpro.com",
            "password": "admin123",
        })
        resp = client.get("/admin/security/me")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["user"]["email"] == "admin@dynamicpro.com"

    def test_me_without_session(self, client):
        resp = client.get("/admin/security/me")
        assert resp.status_code in (401, 403)

    def test_me_with_invalid_header_token(self, client):
        resp = client.get("/admin/security/me",
                          headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code in (401, 403)

    def test_token_refresh_requires_valid_token(self, client):
        resp = client.post("/admin/security/token/refresh",
                           json={"refresh_token": "invalid.refresh.token"})
        assert resp.status_code in (401, 403)


class TestSession:
    """Session management."""

    def test_list_sessions(self, client):
        # Login first to create a session
        client.post("/admin/login", json={
            "email": "admin@dynamicpro.com",
            "password": "admin123",
        })
        resp = client.get("/admin/security/sessions")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert isinstance(data["sessions"], list)

    def test_session_list_requires_auth(self, client):
        resp = client.get("/admin/security/sessions")
        assert resp.status_code in (401, 403)
