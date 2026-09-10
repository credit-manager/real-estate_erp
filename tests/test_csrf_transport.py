"""Regression coverage for CSRF token recovery in the browser SPA."""


def test_authenticated_admin_response_exposes_csrf_header(master_client):
    response = master_client.get("/admin/security/me")
    assert response.status_code == 200
    token = response.headers.get("X-CSRF-Token")
    assert token
    assert len(token) >= 32
