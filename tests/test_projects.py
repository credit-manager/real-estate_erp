"""Projects module tests — project management, job costing, schedule."""
import pytest
import os


@pytest.mark.smoke
class TestProjects:
    """Project CRUD and management tests."""

    def test_create_project(self, auth_client):
        resp = auth_client.post("/api/projects", json={
            "name": f"مشروع اختبار-{os.urandom(3).hex()}",
            "location": "جدة",
            "status": "active",
            "priority": "high",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"].startswith("مشروع اختبار")

    def test_list_projects(self, auth_client):
        resp = auth_client.get("/api/projects")
        assert resp.status_code == 200

    def test_job_costing(self, auth_client):
        # Create project first
        proj = auth_client.post("/api/projects", json={
            "name": "مشروع تكلفة",
            "location": "الدمام",
        }).get_json()
        resp = auth_client.get(f"/api/projects/{proj['id']}/job-costing")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_category" in data
        assert "total_budget" in data
        assert "total_actual" in data

    def test_project_schedule(self, auth_client):
        proj = auth_client.post("/api/projects", json={
            "name": "مشروع جدولة",
            "location": "الخبر",
        }).get_json()
        resp = auth_client.get(f"/api/projects/{proj['id']}/schedule")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "phases" in data
        assert "overall_completion" in data
