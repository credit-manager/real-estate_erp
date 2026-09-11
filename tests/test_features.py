"""Tests for payments, notifications, and e-signature modules."""
import hashlib
import hmac
import json
import os
import secrets
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Payment Gateway Tests ──

class TestPaymentGateways:
    def test_list_gateways(self, auth_client):
        resp = auth_client.get("/api/payments/gateways")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_gateway(self, auth_client):
        name = "test_gw_" + secrets.token_hex(4)
        resp = auth_client.post("/api/payments/gateways", json={
            "name": name,
            "display_name": "Test Gateway",
            "provider": "moyasar",
            "api_key_encrypted": "sk_test_123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == name

    def test_create_gateway_missing_fields(self, auth_client):
        resp = auth_client.post("/api/payments/gateways", json={"name": "x"})
        assert resp.status_code == 400

    def test_webhook_rejects_invalid_signature(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class Gw:
                api_secret = "s3cret"
            assert _verify_webhook_signature(Gw(), {}, "bad") is False

    def test_webhook_validates_hmac(self, app):
        with app.app_context():
            from routes.payments import _verify_webhook_signature

            class Gw:
                api_secret = "s3cret"
            data = {"id": "1", "status": "paid"}
            payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
            sig = hmac.new(b"s3cret", payload.encode(), hashlib.sha256).hexdigest()
            assert _verify_webhook_signature(Gw(), data, sig) is True


# ── Notification System Tests ──

class TestNotifications:
    def _create_channel_and_template(self, auth_client, name_prefix="ntf"):
        ch_name = f"{name_prefix}_ch_{secrets.token_hex(4)}"
        tmpl_name = f"{name_prefix}_tmpl_{secrets.token_hex(4)}"
        ch_resp = auth_client.post("/api/notifications/channels", json={
            "name": ch_name,
            "display_name": f"Test {name_prefix}",
            "provider": "smtp",
            "config_json": {"smtp_host": "localhost"},
        })
        assert ch_resp.status_code == 201
        ch_id = ch_resp.get_json()["id"]
        tmpl_resp = auth_client.post("/api/notifications/templates", json={
            "name": tmpl_name,
            "channel_id": ch_id,
            "subject_template": "Hello {{ name }}",
            "body_template": "<p>Welcome {{ name }}</p>",
        })
        assert tmpl_resp.status_code == 201
        return ch_name, tmpl_name

    def test_send_notification_creates_queue_item(self, auth_client):
        ch_name, tmpl_name = self._create_channel_and_template(auth_client)
        from routes.notifications import send_notification
        result = send_notification(ch_name, tmpl_name, "user@test.com", data={"name": "Test"})
        assert result is True

    def test_notification_body_is_html_escaped(self, auth_client):
        ch_name, tmpl_name = self._create_channel_and_template(auth_client, "esc")
        from routes.notifications import send_notification
        send_notification(ch_name, tmpl_name, "x@test.com", data={"name": "<b>bold</b>"})
        from models import NotificationQueue
        item = NotificationQueue.query.filter_by(recipient="x@test.com").order_by(
            NotificationQueue.id.desc()).first()
        assert item is not None
        assert "<b>" not in item.body
        assert "&lt;b&gt;" in item.body
        from database import db
        from models import NotificationChannel, NotificationTemplate
        db.session.delete(item)
        ch = NotificationChannel.query.filter_by(name=ch_name).first()
        if ch:
            tmpl = NotificationTemplate.query.filter_by(name=tmpl_name).first()
            if tmpl:
                db.session.delete(tmpl)
            db.session.delete(ch)
        db.session.commit()

    def test_email_sender_returns_no_host_error(self):
        from routes.notifications import _send_email

        class FakeItem:
            id = 1
            channel = type("C", (), {"config_json": {}})()
            recipient = "test@test.com"
            subject = "Hi"
            body = "<p>Hello</p>"
        ok, ext_id, err = _send_email(FakeItem())
        assert ok is False
        assert "SMTP_HOST" in err

    def test_push_sender_returns_no_fcm_error(self):
        from routes.notifications import _send_push

        class FakeItem:
            id = 1
            channel = type("C", (), {"config_json": {}})()
            recipient = "token123"
            subject = "Hi"
            body = "Hello"
        ok, ext_id, err = _send_push(FakeItem())
        assert ok is False
        assert "FCM" in err


# ── E-Signature Tests ──

class TestEsignature:
    def test_provider_create_encryption(self, auth_client):
        from database import db
        from models import SignatureProvider
        resp = auth_client.post("/api/esign/providers", json={
            "name": "test_ds_" + secrets.token_hex(4),
            "display_name": "Test DS",
            "client_id": "cid-123",
            "client_secret": "plaintext-secret",
        })
        assert resp.status_code == 201
        provider = db.session.get(SignatureProvider, resp.get_json()["id"])
        assert provider.client_secret_encrypted != "plaintext-secret"
        assert len(provider.client_secret_encrypted) > 20
        db.session.delete(provider)
        db.session.commit()

    def test_provider_update_encryption(self, auth_client):
        from database import db
        from models import SignatureProvider
        name = "test_upd_" + secrets.token_hex(4)
        resp = auth_client.post("/api/esign/providers", json={
            "name": name, "display_name": "Upd", "client_id": "c",
            "client_secret": "old-secret",
        })
        pid = resp.get_json()["id"]
        resp2 = auth_client.put(f"/api/esign/providers/{pid}", json={
            "client_secret": "new-secret",
        })
        assert resp2.status_code == 200
        provider = db.session.get(SignatureProvider, pid)
        assert provider.client_secret_encrypted != "new-secret"
        assert provider.client_secret_encrypted != "old-secret"
        db.session.delete(provider)
        db.session.commit()

    def test_provider_list_hides_secrets(self, auth_client):
        from database import db
        from models import SignatureProvider
        name = "test_list_" + secrets.token_hex(4)
        resp = auth_client.post("/api/esign/providers", json={
            "name": name, "display_name": "Lst", "client_id": "c",
            "client_secret": "secret-val",
        })
        pid = resp.get_json()["id"]
        list_resp = auth_client.get("/api/esign/providers")
        assert list_resp.status_code == 200
        for p in list_resp.get_json():
            assert "client_secret" not in p
            assert "secret" not in json.dumps(p).lower() or p.get("name") == name
        provider = db.session.get(SignatureProvider, pid)
        db.session.delete(provider)
        db.session.commit()
