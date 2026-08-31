"""HR module tests — employees, departments, attendance, leaves."""
import pytest
import os


@pytest.mark.hr
class TestEmployees:
    """Employee CRUD tests."""

    def test_create_employee(self, auth_client):
        resp = auth_client.post("/api/employees", json={
            "full_name": "موظف اختباري",
            "national_id": f"10{os.urandom(7).hex()[:8]}",
            "phone": "0501111222",
            "email": "emp@test.com",
            "department": "ال信息技术",
            "position": "مبرمج",
            "salary": 15000,
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["full_name"] == "موظف اختباري"
        assert data["salary"] == 15000

    def test_list_employees(self, auth_client):
        resp = auth_client.get("/api/employees")
        assert resp.status_code == 200

    def test_update_employee(self, auth_client):
        create = auth_client.post("/api/employees", json={
            "full_name": "موظف للتعديل",
            "national_id": f"10{os.urandom(7).hex()[:8]}",
            "salary": 10000,
        })
        emp_id = create.get_json()["id"]
        resp = auth_client.put(f"/api/employees/{emp_id}", json={
            "salary": 12000,
            "position": "manager",
        })
        assert resp.status_code == 200
        assert resp.get_json()["salary"] == 12000

    def test_delete_employee(self, auth_client):
        create = auth_client.post("/api/employees", json={
            "full_name": "موظف للحذف",
            "national_id": f"10{os.urandom(7).hex()[:8]}",
        })
        emp_id = create.get_json()["id"]
        resp = auth_client.delete(f"/api/employees/{emp_id}")
        assert resp.status_code == 200


@pytest.mark.hr
class TestDepartments:
    """Department tests."""

    def test_list_departments(self, auth_client):
        resp = auth_client.get("/api/hr/departments")
        assert resp.status_code == 200

    def test_create_department(self, auth_client):
        resp = auth_client.post("/api/hr/departments", json={
            "name": f"قسم اختبار-{os.urandom(3).hex()}",
        })
        assert resp.status_code in (200, 201)


@pytest.mark.hr
class TestAttendance:
    """Attendance tests."""

    def test_list_attendance(self, auth_client):
        resp = auth_client.get("/api/hr/attendance")
        assert resp.status_code == 200


@pytest.mark.hr
class TestLeaves:
    """Leave request tests."""

    def test_list_leaves(self, auth_client):
        resp = auth_client.get("/api/hr/leaves")
        assert resp.status_code == 200
