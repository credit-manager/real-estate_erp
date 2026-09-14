# -*- coding: utf-8 -*-
"""Tests: effective branding — owner logo vs licensed-company logo."""
from datetime import date, timedelta

import pytest

from database import db
import utils.settings as settings
import utils.branding as branding


def _seed_customer(app, end_days_from_now, status="active", name="BuyCo"):
    from licensing.models import LicCompany, LicPlan, LicSubscription
    with app.app_context():
        plan = LicPlan(code="P-" + name, name="Plan", name_ar="خطة")
        db.session.add(plan)
        db.session.flush()
        company = LicCompany(name=name, db_name="db_" + name.lower(), status="active")
        db.session.add(company)
        db.session.flush()
        sub = LicSubscription(
            company_id=company.id, plan_id=plan.id,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=end_days_from_now),
            status=status,
        )
        db.session.add(sub)
        db.session.commit()


def test_effective_logo_owner_when_no_customer(app, db_session):
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "1")
    settings.set("branding_customer_logo", "https://cust.example/logo.png")
    db.session.commit()
    assert branding.effective_logo() == "https://owner.example/logo.png"


def test_effective_logo_customer_when_override_on(app, db_session):
    _seed_customer(app, 365)
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "1")
    settings.set("branding_customer_logo", "data:image/png;base64,iVBORw0KGgo=")
    db.session.commit()
    assert branding.effective_logo() == "data:image/png;base64,iVBORw0KGgo="
    # The hook also affects settings.get("system_logo") used by PDF / prints.
    assert settings.get("system_logo") == "data:image/png;base64,iVBORw0KGgo="


def test_effective_logo_owner_when_override_off(app, db_session):
    _seed_customer(app, 365)
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "0")
    settings.set("branding_customer_logo", "https://cust.example/logo.png")
    db.session.commit()
    assert branding.effective_logo() == "https://owner.example/logo.png"


def test_effective_logo_owner_when_customer_logo_empty(app, db_session):
    _seed_customer(app, 365)
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "1")
    settings.set("branding_customer_logo", "")
    db.session.commit()
    assert branding.effective_logo() == "https://owner.example/logo.png"


def test_effective_logo_owner_when_subscription_expired(app, db_session):
    _seed_customer(app, -20)
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "1")
    settings.set("branding_customer_logo", "https://cust.example/logo.png")
    db.session.commit()
    assert branding.effective_logo() == "https://owner.example/logo.png"


def test_effective_logo_owner_when_company_suspended(app, db_session):
    from licensing.models import LicCompany
    with app.app_context():
        LicCompany.query.filter_by(db_name="db_buyco").update({"status": "suspended"})
        db.session.commit()
    settings.set("system_logo", "https://owner.example/logo.png")
    settings.set("branding_override", "1")
    settings.set("branding_customer_logo", "https://cust.example/logo.png")
    db.session.commit()
    assert branding.effective_logo() == "https://owner.example/logo.png"


def test_valid_logo():
    assert branding.valid_logo("") is None
    assert branding.valid_logo("   ") is None
    assert branding.valid_logo("https://example.com/logo.png") is None
    assert branding.valid_logo("http://example.com/a.png") is None
    assert branding.valid_logo("data:image/png;base64,AAAA") is None
    assert branding.valid_logo("data:image/svg+xml;base64,AAAA") is None
    assert branding.valid_logo("ftp://example.com/logo.png") == "settings.logoInvalid"
    assert branding.valid_logo("not-a-url") == "settings.logoInvalid"
    assert branding.valid_logo("data:text/plain;base64,AAAA") == "settings.logoInvalid"
    big = "data:image/png;base64," + ("A" * (branding.LOGO_MAX_LENGTH + 10))
    assert branding.valid_logo(big) == "settings.logoTooLarge"


def test_branding_api_save_and_override(app, client):
    from werkzeug.security import generate_password_hash
    from models import User

    with app.app_context():
        db.session.add(User(username="boss", email="boss@t.local", full_name="المدير",
                            role="admin", password_hash=generate_password_hash("x"),
                            is_active=True))
        db.session.commit()
        uid = User.query.filter_by(username="boss").first().id

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = "admin"
        sess["username"] = "boss"
        sess["full_name"] = "المدير"

    _seed_customer(client.application, 365, name="ApiCo")

    resp = client.post("/general-settings/api/branding", json={
        "override": True,
        "customer_logo": "https://apico.example/logo.png",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["branding"]["override"] is True
    assert data["branding"]["customer_logo"] == "https://apico.example/logo.png"

    resp = client.get("/general-settings/api")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["branding"]["effective_logo"] == "https://apico.example/logo.png"
    assert data["branding"]["customer"]["name"] == "ApiCo"


def test_branding_api_rejects_invalid_logo(app, client):
    from werkzeug.security import generate_password_hash
    from models import User

    with app.app_context():
        db.session.add(User(username="boss2", email="boss2@t.local", full_name="المدير",
                            role="admin", password_hash=generate_password_hash("x"),
                            is_active=True))
        db.session.commit()
        uid = User.query.filter_by(username="boss2").first().id

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = "admin"
        sess["username"] = "boss2"
        sess["full_name"] = "المدير"

    resp = client.post("/general-settings/api/branding", json={
        "override": True,
        "customer_logo": "javascript:alert(1)",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error_key"] == "settings.logoInvalid"