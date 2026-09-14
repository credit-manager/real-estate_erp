# -*- coding: utf-8 -*-
"""Tests: smart reorder recommendations, project KPIs, cloud push."""
from datetime import date, timedelta

from database import db
from models import Item, ItemStock, Project, StockMovement, Warehouse
from utils import cloud_backup
from utils.analytics import (
    compute_alerts, compute_project_kpis, compute_reorder_recommendations,
)


class _S:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)


def test_reorder_recommendations_use_consumption(app):
    with app.app_context():
        wh = Warehouse(code="WH2", name="مخزن")
        db.session.add(wh)
        db.session.flush()
        it = Item(code="ITM-2", name="خامة ب", reorder_level=5, is_active=True)
        db.session.add(it)
        db.session.flush()
        db.session.add(ItemStock(item_id=it.id, warehouse_id=wh.id, quantity=2, avg_cost=10))
        for _ in range(5):
            db.session.add(StockMovement(
                item_id=it.id, warehouse_id=wh.id,
                movement_type="out", quantity=20,
            ))
        db.session.commit()

        recs = compute_reorder_recommendations()
        match = [r for r in recs if r["id"] == it.id]
        assert match, "item must appear in reorder recommendations"
        row = match[0]
        assert row["quantity"] == 2
        assert row["monthly_consumption"] > 0
        assert row["suggested_order"] > 0
        assert row["coverage_days"] is not None


def test_reorder_no_consumption_still_suggests(app):
    with app.app_context():
        wh = Warehouse(code="WH3", name="مخزن ٣")
        db.session.add(wh)
        db.session.flush()
        it = Item(code="ITM-3", name="خامة ج", reorder_level=5, is_active=True)
        db.session.add(it)
        db.session.flush()
        db.session.add(ItemStock(item_id=it.id, warehouse_id=wh.id, quantity=1, avg_cost=0))
        db.session.commit()

        recs = compute_reorder_recommendations()
        match = [r for r in recs if r["id"] == it.id]
        assert match
        row = match[0]
        assert row["monthly_consumption"] == 0
        assert row["coverage_days"] is None
        assert row["suggested_order"] == 4  # الحد الأدنى − الرصيد


def test_project_kpis_flags_at_risk(app):
    with app.app_context():
        db.session.add(Project(
            name="برج تجريبي", status="active", budget=1000, spent=1300,
            completion=30, deadline=date.today() - timedelta(days=1),
        ))
        db.session.commit()

        kpi = compute_project_kpis()
        assert kpi["summary"]["tracked"] >= 1
        assert kpi["summary"]["at_risk"] >= 1
        proj = kpi["projects"][0]
        assert proj["at_risk"]
        assert "budget_overrun" in proj["risk_reasons"]
        assert "deadline_passed" in proj["risk_reasons"]
        assert proj["budget_utilization"] == 130.0


def test_project_risk_alert_in_compute_alerts(app):
    with app.app_context():
        db.session.add(Project(
            name="مشروع متعثر", status="active", budget=100, spent=400,
            completion=10, deadline=date.today(),
        ))
        db.session.commit()
        types = {x["type"] for x in compute_alerts()["alerts"]}
        assert "project_at_risk" in types


def test_cloud_push_disabled():
    ok, msg = cloud_backup.push_backup(b"x", "f.bin", _S({}))
    assert ok is False and msg == "cloud.disabled"


def test_cloud_push_webdav_ok(monkeypatch):
    monkeypatch.setattr(cloud_backup, "webdav_put", lambda *a, **k: 201)
    ok, msg = cloud_backup.push_backup(
        b"x", "f.bin",
        _S({"backup_cloud_enabled": "1", "backup_cloud_type": "webdav"}),
    )
    assert ok is True and msg == ""


def test_cloud_push_webdav_error(monkeypatch):
    monkeypatch.setattr(cloud_backup, "webdav_put", lambda *a, **k: 500)
    ok, msg = cloud_backup.push_backup(
        b"x", "f.bin",
        _S({"backup_cloud_enabled": "1", "backup_cloud_type": "webdav"}),
    )
    assert ok is False and msg == "HTTP 500"


def test_cloud_push_s3_ok(monkeypatch):
    monkeypatch.setattr(cloud_backup, "s3_put", lambda *a, **k: 200)
    ok, msg = cloud_backup.push_backup(
        b"x", "f.bin",
        _S({
            "backup_cloud_enabled": "1", "backup_cloud_type": "s3",
            "backup_cloud_url": "https://s3.amazonaws.com",
            "backup_cloud_bucket": "bkt",
        }),
    )
    assert ok is True


def test_cloud_push_s3_failure_propagates_message(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network unreachable")
    monkeypatch.setattr(cloud_backup, "s3_put", boom)
    ok, msg = cloud_backup.push_backup(
        b"x", "f.bin",
        _S({"backup_cloud_enabled": "1", "backup_cloud_type": "s3"}),
    )
    assert ok is False and "network unreachable" in msg


def test_cloud_push_unknown_type():
    ok, msg = cloud_backup.push_backup(
        b"x", "f.bin",
        _S({"backup_cloud_enabled": "1", "backup_cloud_type": "ftp"}),
    )
    assert ok is False and msg == "cloud.unknown_type"