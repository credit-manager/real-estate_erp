# -*- coding: utf-8 -*-
"""Remote management tests — heartbeat auth, commands, suspend, sync."""
import uuid


def _cid():
    return f"DP-TEST-{uuid.uuid4().hex[:8].upper()}"


def _register(client, company_id, name="Test Device"):
    cid = _cid()
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid,
        "company_id": company_id,
        "client_name": name,
        "client_type": "desktop",
        "os_info": "TestOS 1.0",
        "local_ip": "10.0.0.5",
        "mac_address": "AA:BB:CC:DD:EE:FF",
    })
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["ok"] is True
    assert data.get("client_secret"), "first registration must return a secret"
    return cid, data["client_secret"]


def _db_id(master_client, cid):
    resp = master_client.get("/api/remote/clients")
    assert resp.status_code == 200
    for c in resp.get_json():
        if c["client_id"] == cid:
            return c["id"]
    raise AssertionError(f"client {cid} not listed")


def test_heartbeat_registers_and_returns_secret(client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    assert cid and secret


def test_heartbeat_requires_secret_after_registration(client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    # No secret -> 401
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    })
    assert resp.status_code == 401
    # Wrong secret -> 401
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
    # Right secret -> 200
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200
    assert resp.get_json()["pending_commands"] == []


def test_heartbeat_validates_input(client):
    resp = client.post("/api/remote/heartbeat", json={})
    assert resp.status_code == 400
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": _cid(), "company_id": 999999999,
    })
    assert resp.status_code == 404


def test_command_roundtrip(client, master_client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    dbid = _db_id(master_client, cid)
    # Queue a command
    resp = master_client.post(f"/api/remote/clients/{dbid}/command", json={
        "command": "update_config", "payload": {"k": "v"},
    })
    assert resp.status_code == 200
    cmd_id = resp.get_json()["command"]["id"]
    # Agent fetches it on next heartbeat
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": f"Bearer {secret}"})
    pending = resp.get_json()["pending_commands"]
    assert len(pending) == 1 and pending[0]["id"] == cmd_id
    # Agent reports result
    resp = client.post("/api/remote/command-result",
                       json={"command_id": cmd_id, "status": "executed"},
                       headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200
    # No longer pending
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200  # throttled or empty
    body = resp.get_json()
    assert body.get("throttled") is True or body.get("pending_commands") == []


def test_command_result_requires_auth(client, master_client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    dbid = _db_id(master_client, cid)
    cmd_id = master_client.post(
        f"/api/remote/clients/{dbid}/command",
        json={"command": "lock", "payload": {}}).get_json()["command"]["id"]
    # No auth -> 401, command stays pending
    resp = client.post("/api/remote/command-result",
                       json={"command_id": cmd_id, "status": "executed"})
    assert resp.status_code == 401
    # Unknown command -> 404
    resp = client.post("/api/remote/command-result",
                       json={"command_id": 999999999, "status": "executed"},
                       headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 404


def test_suspend_blocks_heartbeat(client, master_client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    dbid = _db_id(master_client, cid)
    assert master_client.post(f"/api/remote/clients/{dbid}/suspend").status_code == 200
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 403
    assert master_client.post(f"/api/remote/clients/{dbid}/reactivate").status_code == 200
    resp = client.post("/api/remote/heartbeat", json={
        "client_id": cid, "company_id": sample_company["id"],
    }, headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200


def test_sync_requires_auth_and_logs(client, master_client, sample_company):
    cid, secret = _register(client, sample_company["id"])
    # No auth -> 401
    resp = client.post("/api/remote/sync", json={
        "client_id": cid, "sync_type": "push", "records": [{"a": 1}],
    })
    assert resp.status_code == 401
    # With auth -> logged
    resp = client.post("/api/remote/sync", json={
        "client_id": cid, "sync_type": "push", "records": [{"a": 1}],
    }, headers={"Authorization": f"Bearer {secret}"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_clients_list_has_pending_counts(master_client, client, sample_company):
    cid, _secret = _register(client, sample_company["id"])
    dbid = _db_id(master_client, cid)
    master_client.post(f"/api/remote/clients/{dbid}/command",
                       json={"command": "lock", "payload": {}})
    resp = master_client.get("/api/remote/clients")
    assert resp.status_code == 200
    row = next(c for c in resp.get_json() if c["client_id"] == cid)
    assert row["pending_commands_count"] == 1


def test_invalid_command_rejected(master_client, client, sample_company):
    cid, _secret = _register(client, sample_company["id"])
    dbid = _db_id(master_client, cid)
    resp = master_client.post(f"/api/remote/clients/{dbid}/command",
                              json={"command": "format_disk", "payload": {}})
    assert resp.status_code == 400


class TestAgentInbox:
    """Sync-inbox behavior (no server needed)."""

    def _agent(self, tmp_path):
        from remote_sync import RemoteSyncAgent

        agent = RemoteSyncAgent.__new__(RemoteSyncAgent)
        agent._inbox_dir = tmp_path
        return agent

    def test_sync_data_queued_and_drained(self, tmp_path):
        agent = self._agent(tmp_path)
        agent._handle_sync_data({"batch_id": "b1", "records": [{"x": 1}]})
        items = list(agent.drain_inbox())
        assert len(items) == 1
        fname, payload = items[0]
        assert payload["records"] == [{"x": 1}]
        assert agent.ack_inbox(fname) is True
        assert list(agent.drain_inbox()) == []

    def test_ack_rejects_path_traversal(self, tmp_path):
        agent = self._agent(tmp_path)
        assert agent.ack_inbox("../secret.json") is False
        assert agent.ack_inbox("nope.json") is False

    def test_inbox_pruned_to_cap(self, tmp_path):
        agent = self._agent(tmp_path)
        for i in range(105):
            agent._handle_sync_data({"batch_id": f"b{i}", "records": []})
        assert len(list(agent.drain_inbox())) == 100
