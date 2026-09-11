"""Security tests — encryption, webhook verification, XSS prevention, LIKE escaping."""
import hashlib
import hmac
import json
import os
import sys
import secrets

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        from utils.crypto import encrypt_field, decrypt_field
        key = secrets.token_hex(16)
        secret = "my-super-secret-client-secret-1234"
        encrypted = encrypt_field(secret, key)
        assert encrypted != secret
        decrypted = decrypt_field(encrypted, key)
        assert decrypted == secret

    def test_encrypt_empty_returns_empty(self):
        from utils.crypto import encrypt_field, decrypt_field
        assert encrypt_field("", "key") == ""
        assert encrypt_field(None, "key") is None
        assert decrypt_field("", "key") == ""
        assert decrypt_field(None, "key") is None

    def test_different_keys_fail_decrypt(self):
        from utils.crypto import encrypt_field, decrypt_field
        encrypted = encrypt_field("secret", "key1")
        with pytest.raises(Exception):
            decrypt_field(encrypted, "key2")

    def test_deterministic_different_ciphertext(self):
        from utils.crypto import encrypt_field
        key = "same-key"
        a = encrypt_field("test", key)
        b = encrypt_field("test", key)
        assert a != b


class TestWebhookSignature:
    def test_valid_signature(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class FakeGateway:
                api_secret = "webhook-secret-123"

            data = {"id": "txn_123", "status": "paid", "amount": 100}
            payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
            sig = hmac.new(b"webhook-secret-123", payload.encode(), hashlib.sha256).hexdigest()
            assert _verify_webhook_signature(FakeGateway(), data, sig) is True

    def test_invalid_signature(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class FakeGateway:
                api_secret = "webhook-secret-123"

            data = {"id": "txn_123"}
            assert _verify_webhook_signature(FakeGateway(), data, "bad-sig") is False

    def test_missing_signature(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class FakeGateway:
                api_secret = "webhook-secret-123"

            assert _verify_webhook_signature(FakeGateway(), {}, None) is False

    def test_no_secret_configured(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class FakeGateway:
                api_secret = ""

            assert _verify_webhook_signature(FakeGateway(), {}, "sig") is False


class TestEsignEncryption:
    def test_provider_secret_encrypted_on_create(self, auth_client):
        from database import db
        from models import SignatureProvider
        resp = auth_client.post("/api/esign/providers", json={
            "name": "test_docusign_" + secrets.token_hex(4),
            "display_name": "Test DocuSign",
            "client_id": "client-abc",
            "client_secret": "super-secret-oauth-token",
            "webhook_secret": "webhook-verify-secret",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        provider = db.session.get(SignatureProvider, data["id"])
        assert provider.client_id == "client-abc"
        assert provider.client_secret_encrypted != "super-secret-oauth-token"
        assert provider.webhook_secret_encrypted != "webhook-verify-secret"
        db.session.delete(provider)
        db.session.commit()


class TestNotificationSSTI:
    def test_template_renders_safely(self, auth_client):
        from database import db
        from models import NotificationChannel, NotificationTemplate, NotificationQueue

        ch_name = "test_ssti_" + secrets.token_hex(4)
        tmpl_name = "test_ssti_tmpl_" + secrets.token_hex(4)
        ch = NotificationChannel(name=ch_name, display_name="Test SSTI Channel", is_active=True)
        db.session.add(ch)
        db.session.flush()

        tmpl = NotificationTemplate(
            name=tmpl_name,
            channel_id=ch.id,
            subject_template="Hello {{ name }}",
            body_template="<p>{{ name }}</p>",
            is_active=True,
        )
        db.session.add(tmpl)
        db.session.commit()

        from routes.notifications import send_notification
        result = send_notification(
            ch_name, tmpl_name,
            "test@example.com",
            data={"name": "<script>alert('xss')</script>"},
        )
        assert result is True

        item = NotificationQueue.query.filter_by(
            recipient="test@example.com"
        ).order_by(NotificationQueue.id.desc()).first()
        assert item is not None
        assert "<script>" not in item.body
        assert "&lt;script&gt;" in item.body

        db.session.delete(item)
        db.session.delete(tmpl)
        db.session.delete(ch)
        db.session.commit()


class TestLikeEscaping:
    def test_percent_not_match_all(self, auth_client):
        from database import db
        from models import RealEstateUnit, Project, Building
        import uuid

        proj = Project(name=f"esc_proj_{uuid.uuid4().hex[:6]}", status="active")
        db.session.add(proj)
        db.session.flush()
        bld = Building(name="B1", project_id=proj.id)
        db.session.add(bld)
        db.session.flush()
        u1 = RealEstateUnit(
            unit_code=f"ESC-{uuid.uuid4().hex[:4]}",
            project_id=proj.id, building_id=bld.id,
            area=100, price=1000000,
            status="available",
        )
        u2 = RealEstateUnit(
            unit_code=f"XYZ-{uuid.uuid4().hex[:4]}",
            project_id=proj.id, building_id=bld.id,
            area=200, price=2000000,
            status="available",
        )
        db.session.add_all([u1, u2])
        db.session.commit()

        resp = auth_client.get("/api/units?search=%25")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) < RealEstateUnit.query.count()

        db.session.delete(u1)
        db.session.delete(u2)
        db.session.delete(bld)
        db.session.delete(proj)
        db.session.commit()
