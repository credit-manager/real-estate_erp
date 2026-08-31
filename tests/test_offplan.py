"""Off-plan module tests — milestones, DSP plans, title deeds."""
import pytest
import os


@pytest.mark.offplan
class TestMilestones:
    """Construction milestone tests."""

    def test_create_milestone(self, auth_client, sample_project):
        resp = auth_client.post("/api/offplan/milestones", json={
            "project_id": sample_project["id"],
            "name": "أعمال الحفر",
            "target_date": "2026-12-01",
            "weight": 20,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "أعمال الحفر"
        assert data["weight"] == 20

    def test_complete_milestone(self, auth_client, sample_project):
        create = auth_client.post("/api/offplan/milestones", json={
            "project_id": sample_project["id"],
            "name": "أعمال الأساسات",
            "target_date": "2026-06-01",
            "weight": 30,
        })
        mid = create.get_json()["id"]
        resp = auth_client.put(f"/api/offplan/milestones/{mid}", json={
            "completion_pct": 100,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["completion_pct"] == 100

    def test_list_milestones(self, auth_client, sample_project):
        resp = auth_client.get(f"/api/offplan/milestones?project_id={sample_project['id']}")
        assert resp.status_code == 200


@pytest.mark.offplan
class TestDSPPlans:
    """DSP (Deferred Payment) plan tests."""

    def test_create_dsp_plan(self, auth_client, sample_project):
        # Create milestone first
        ms = auth_client.post("/api/offplan/milestones", json={
            "project_id": sample_project["id"],
            "name": "مرحلة الاكتمال",
            "target_date": "2027-01-01",
            "weight": 50,
        }).get_json()
        resp = auth_client.post("/api/offplan/dsp", json={
            "project_id": sample_project["id"],
            "milestone_id": ms["id"],
            "name": "دفعة الحجز",
            "due_pct": 10,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["due_pct"] == 10
        assert data["milestone_id"] == ms["id"]

    def test_dsp_check(self, auth_client, sample_project):
        resp = auth_client.get("/api/offplan/dsp/check/1")
        assert resp.status_code == 200
