# -*- coding: utf-8 -*-
"""Phase 10 — Health check + basic smoke tests."""
import json


def test_health_endpoint(client):
    """GET /health returns 200 with DB status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_root_redirects(client):
    """GET / redirects to login."""
    resp = client.get("/")
    assert resp.status_code in (302, 308)


def test_admin_requires_auth(client):
    """GET /admin/security/me without token returns 401."""
    resp = client.get("/admin/security/me")
    assert resp.status_code in (401, 403)
