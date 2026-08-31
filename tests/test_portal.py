"""Customer portal tests — no-auth lookup, contract details."""
import pytest


@pytest.mark.portal
class TestPortalLookup:
    """Portal contract lookup tests."""

    def test_portal_lookup_no_auth(self, client):
        resp = client.get("/api/portal/lookup?contract_number=NONEXISTENT")
        assert resp.status_code in (200, 404)

    def test_portal_lookup_empty(self, client):
        resp = client.get("/api/portal/lookup")
        assert resp.status_code in (200, 400, 404)


@pytest.mark.portal
class TestPortalUI:
    """Portal UI page tests."""

    def test_portal_page_loads(self, client):
        resp = client.get("/portal")
        assert resp.status_code == 200
