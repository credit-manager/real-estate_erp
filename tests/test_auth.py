# -*- coding: utf-8 -*-
"""Authentication tests for company sessions and the Master Control Center."""


def test_company_login_success(auth_client):
    response = auth_client.get("/api/me")
    data = response.get_json()
    assert response.status_code == 200
    assert data["authenticated"] is True
    assert data["type"] == "employee"
    assert data["csrf_token"]


def test_company_me_without_session(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.get_json()["authenticated"] is False


def test_master_login_success(master_client):
    response = master_client.get("/admin/security/me")
    data = response.get_json()
    assert response.status_code == 200
    assert data["success"] is True
    assert data["user"]["role"] == "super_admin"


def test_master_session_contains_no_jwt_material(master_client):
    with master_client.session_transaction() as sess:
        assert "master_access_token" not in sess
        assert "master_refresh_token" not in sess
        assert sess.get("master_jti")


def test_master_session_is_revocable(master_client):
    with master_client.session_transaction() as sess:
        jti = sess.get("master_jti")
    assert jti

    with master_client.application.app_context():
        from database import db
        from security.models import MasterSession

        row = MasterSession.query.filter_by(jti=jti).first()
        assert row is not None
        row.revoked = True
        db.session.commit()

    response = master_client.get("/admin/security/me")
    assert response.status_code == 401


def test_master_me_without_session(client):
    response = client.get("/admin/security/me")
    assert response.status_code == 401


def test_master_invalid_refresh_token_is_rejected(master_client):
    response = master_client.post(
        "/admin/security/token/refresh",
        json={"refresh_token": "invalid.refresh.token"},
    )
    assert response.status_code in (401, 403)


def test_master_session_list(master_client):
    response = master_client.get("/admin/security/sessions")
    data = response.get_json()
    assert response.status_code == 200
    assert data["success"] is True
    assert isinstance(data["sessions"], list)
