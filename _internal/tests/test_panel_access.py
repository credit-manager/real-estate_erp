# -*- coding: utf-8 -*-
"""Tests: master control panel access from the main app."""
import os

import pytest
from flask import render_template
from sqlalchemy import select

_INTERNAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _template_dir(app):
    app.template_folder = os.path.join(_INTERNAL, "templates")
    app.static_folder = os.path.join(_INTERNAL, "static")
    from jinja2 import FileSystemLoader
    app.jinja_env.loader = FileSystemLoader(app.template_folder)
    from i18n import make_t
    app.jinja_env.globals.update(
        t=make_t("ar"),
        can=lambda m, a: True,
        csrf_token="tok",
        lang="ar",
        full_name="",
        default_theme="dark",
        system_logo=None,
        system_name="2TO",
        is_dark=False,
        debug=False,
        translations_json="{}",
        permissions_json="{}",
        app_settings_json="{}",
    )
    yield


def test_module_hub_renders_new_tab_target(app):
    with app.test_request_context("/system-hub"):
        cards = [{
            "url": "/admin", "icon": "🛡️",
            "title": "لوحة التحكم المركزية", "sub": "companies",
            "target": "_blank",
        }]
        html = render_template("module_hub.html",
                               hub_title="النظام", hub_sub="", hub_id="system", cards=cards)
        assert 'href="/admin"' in html
        assert 'target="_blank"' in html
        assert "rel=\"noopener\"" in html


def test_module_hub_no_target_when_empty(app):
    with app.test_request_context("/system-hub"):
        cards = [{"url": "/finance", "icon": "💰", "title": "المالية", "sub": "", "target": ""}]
        html = render_template("module_hub.html",
                               hub_title="النظام", hub_sub="", hub_id="system", cards=cards)
        assert 'href="/finance"' in html
        assert "target=" not in html


def _set_identity(client, user_id, role, full_name):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role
        sess["username"] = "u"
        sess["full_name"] = full_name


def test_master_panel_card_admin_only(app, client):
    from werkzeug.security import generate_password_hash
    from database import db
    from models import User

    with app.app_context():
        db.session.add_all([
            User(username="owner", email="owner@test.local", full_name="المالك",
                 role="admin", password_hash=generate_password_hash("x"), is_active=True),
            User(username="clerk", email="clerk@test.local", full_name="موظف",
                 role="employee", password_hash=generate_password_hash("x"), is_active=True),
        ])
        db.session.commit()
        owner_id = db.session.execute(select(User.id).where(User.username == "owner")).scalar_one()
        clerk_id = db.session.execute(select(User.id).where(User.username == "clerk")).scalar_one()

    _set_identity(client, owner_id, "admin", "المالك")
    resp = client.get("/system-hub")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "لوحة التحكم المركزية" in body
    assert 'href="/admin"' in body

    _set_identity(client, clerk_id, "employee", "موظف")
    resp = client.get("/system-hub")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'href="/admin"' not in body