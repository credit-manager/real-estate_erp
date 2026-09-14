# -*- coding: utf-8 -*-
"""Tests for routes/auth.py - Authentication routes."""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestLoginEndpoint:
    """Tests for /login endpoint."""

    @pytest.mark.xfail(reason="Requires login.html template not available in test env")
    def test_get_login_returns_page(self, client):
        """GET /login returns the login page."""
        resp = client.get("/login")
        assert resp.status_code in (200, 302)

    @pytest.mark.xfail(reason="Requires full DB session context")
    def test_post_login_empty_body(self, client):
        """POST /login with empty body returns 401."""
        resp = client.post(
            "/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code in (401, 400)

    @pytest.mark.xfail(reason="Requires full DB session context")
    def test_post_login_invalid_credentials(self, client):
        """POST /login with invalid credentials returns 401."""
        resp = client.post(
            "/login",
            data=json.dumps({"username": "nonexistent", "password": "wrong"}),
            content_type="application/json",
        )
        assert resp.status_code in (401, 400)


class TestLogoutEndpoint:
    """Tests for /logout endpoint."""

    def test_logout_returns_success(self, client):
        """POST /logout always returns success."""
        resp = client.post("/logout")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True


class TestMeEndpoint:
    """Tests for /api/me endpoint."""

    def test_unauthenticated_returns_401(self, client):
        """GET /api/me returns 401 when not authenticated."""
        resp = client.get("/api/me")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data.get("authenticated") is False

    def test_me_returns_json(self, client):
        """GET /api/me returns JSON content type."""
        resp = client.get("/api/me")
        assert resp.content_type.startswith("application/json")
