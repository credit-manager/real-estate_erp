"""Approval workflow module tests."""
import pytest


@pytest.mark.workflow
class TestWorkflowTemplates:
    """Workflow template tests."""

    def test_list_workflow_templates(self, auth_client):
        resp = auth_client.get("/workflow/api/templates")
        assert resp.status_code == 200


@pytest.mark.workflow
class TestApprovalRequests:
    """Approval request tests."""

    def test_list_approval_requests(self, auth_client):
        resp = auth_client.get("/workflow/api/requests")
        assert resp.status_code == 200
