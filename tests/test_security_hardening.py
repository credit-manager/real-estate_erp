from datetime import datetime, timezone

import pytest

from security.rbac import permitted
from security.tokens import decode_token, issue_token_pair


def test_permitted_requires_all_permissions_for_iterable():
    permissions = {"companies.view", "companies.edit"}
    assert permitted(permissions, ["companies.view", "companies.edit"])
    assert not permitted(permissions, ["companies.view", "companies.delete"])


def test_permitted_accepts_single_permission():
    assert permitted({"dashboard.view"}, "dashboard.view")
    assert not permitted({"dashboard.view"}, "system.settings")


def test_permission_required_rejects_empty_declaration():
    from security.rbac import permission_required

    with pytest.raises(ValueError):
        permission_required()


def test_jwt_round_trip_uses_utc_and_required_claims():
    now = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    access, refresh, jti = issue_token_pair(
        master_user_id=7,
        email="admin@example.com",
        name="Admin",
        permissions={"dashboard.view", "system.view"},
        now=now,
    )

    assert jti
    access_payload = decode_token(access, expected_type="access")
    refresh_payload = decode_token(refresh, expected_type="refresh")

    assert access_payload is not None
    assert refresh_payload is not None
    assert access_payload["sub"] == "7"
    assert access_payload["iss"] == "dynamicpro-control-center"
    assert access_payload["typ"] == "access"
    assert set(access_payload["perms"]) == {"dashboard.view", "system.view"}
    assert refresh_payload["typ"] == "refresh"
    assert refresh_payload["jti"] == jti


def test_jwt_rejects_wrong_token_type():
    access, _, _ = issue_token_pair(1, "a@example.com", "A", set())
    assert decode_token(access, expected_type="refresh") is None
