# -*- coding: utf-8 -*-
"""Remote Management API for offline/desktop clients.

Allows the master server to manage offline clients:
- Heartbeat: clients check in periodically
- Commands: admin pushes commands to clients
- Sync: data synchronization between client and server
- Config: push remote configuration updates
"""
import logging
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import or_

from database import db
from licensing.models import (
    RemoteClient, RemoteCommand, RemoteSyncLog,
    LicCompany, LicCompanyUser
)

log = logging.getLogger(__name__)

remote_api_bp = Blueprint("remote_api", __name__, url_prefix="/api/remote")


def _get_master_user():
    """Get current master admin user from session."""
    uid = session.get("master_user_id")
    if not uid:
        return None
    from licensing.models import LicMasterUser
    return db.session.get(LicMasterUser, uid)


def require_master(f):
    """Decorator: require master admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _get_master_user():
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def _generate_client_id():
    return f"DP-{secrets.token_hex(8).upper()}"


def _generate_client_secret():
    return secrets.token_urlsafe(32)


# ── CLIENT ENDPOINTS (called by desktop clients) ────────────

_HEARTBEAT_THROTTLE = {}
def _heartbeat_min_interval():
    try:
        return max(0, int(os.environ.get("REMOTE_HEARTBEAT_MIN_INTERVAL_SEC", "5") or 5))
    except (TypeError, ValueError):
        return 5


_HEARTBEAT_MIN_INTERVAL = 5  # default; evaluated per-request via _heartbeat_min_interval()


@remote_api_bp.route("/heartbeat", methods=["POST"])
def client_heartbeat():
    """Client sends heartbeat with its status.

    Auth and suspension are ALWAYS enforced; throttling only skips the
    expensive command-collection path for authenticated clients.
    """
    import time as _time
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id")
    company_id = data.get("company_id")

    if not client_id or not company_id:
        return jsonify({"error": "client_id and company_id required"}), 400

    client = RemoteClient.query.filter_by(client_id=client_id).first()

    # Authentication: verify client_secret header
    auth_header = request.headers.get("Authorization", "")
    if client:
        # Existing client: verify secret
        if not client.client_secret:
            # Legacy client without secret: generate one and return it
            client.client_secret = _generate_client_secret()
            db.session.commit()
        elif not auth_header.startswith("Bearer ") or auth_header[7:] != client.client_secret:
            return jsonify({"error": "Invalid client_secret"}), 401
        if not client.is_authorized:
            return jsonify({"error": "Client suspended"}), 403
    else:
        # New client: auto-register and return secret
        if not auth_header.startswith("Bearer "):
            # First-time registration: create with new secret
            company = db.session.get(LicCompany, company_id)
            if not company:
                return jsonify({"error": "Company not found"}), 404
            new_secret = _generate_client_secret()
            client = RemoteClient(
                company_id=company_id,
                client_id=client_id,
                client_name=data.get("client_name", "Unknown"),
                client_type=data.get("client_type", "desktop"),
                os_info=data.get("os_info"),
                app_version=data.get("app_version"),
                public_ip=request.remote_addr,
                local_ip=data.get("local_ip"),
                mac_address=data.get("mac_address"),
                client_secret=new_secret,
            )
            db.session.add(client)
            db.session.commit()
            log.info(f"New remote client registered: {client_id} for company {company.name}")
            # Return the secret so client can store it
            return jsonify({
                "ok": True,
                "client_secret": new_secret,
                "server_time": datetime.utcnow().isoformat(),
                "pending_commands": [],
                "remote_config": {},
            })
        else:
            return jsonify({"error": "Client not found. Register first without Authorization header."}), 404

    # Throttle: authenticated clients only (post-auth, so it can never
    # bypass authentication or suspension enforcement).
    import time as _time2
    _now = _time2.time()
    _last = _HEARTBEAT_THROTTLE.get(client_id, 0)
    if _now - _last < _heartbeat_min_interval():
        return jsonify({"ok": True, "throttled": True}), 200
    _HEARTBEAT_THROTTLE[client_id] = _now

    # Update status
    client.last_heartbeat = datetime.utcnow()
    client.public_ip = request.remote_addr
    if data.get("local_ip"):
        client.local_ip = data["local_ip"]
    if data.get("app_version"):
        client.app_version = data["app_version"]
    if data.get("mac_address"):
        client.mac_address = data["mac_address"]
    client.status = "active"

    # Collect pending commands
    pending = RemoteCommand.query.filter_by(
        client_id=client.id, status="pending"
    ).order_by(RemoteCommand.issued_at).all()

    commands_list = [c.to_dict() for c in pending]

    # Mark as sent
    for cmd in pending:
        cmd.status = "sent"

    db.session.commit()

    return jsonify({
        "ok": True,
        "server_time": datetime.utcnow().isoformat(),
        "pending_commands": commands_list,
        "remote_config": client.remote_config or {},
    })


@remote_api_bp.route("/command-result", methods=["POST"])
def command_result():
    """Client reports result of a command."""
    data = request.get_json(silent=True) or {}
    cmd_id = data.get("command_id")
    status = data.get("status", "executed")
    result = data.get("result")

    if not cmd_id:
        return jsonify({"error": "command_id required"}), 400

    cmd = db.session.get(RemoteCommand, cmd_id)
    if not cmd:
        return jsonify({"error": "Command not found"}), 404

    # Verify client authentication
    client = db.session.get(RemoteClient, cmd.client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    auth_header = request.headers.get("Authorization", "")
    if not client.client_secret or not auth_header.startswith("Bearer ") or auth_header[7:] != client.client_secret:
        return jsonify({"error": "Unauthorized"}), 401

    cmd.status = status
    cmd.result = result
    cmd.executed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True})


@remote_api_bp.route("/sync", methods=["POST"])
def client_sync():
    """Client sends sync data (e.g., new records, updates)."""
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id")
    company_id = data.get("company_id")
    sync_type = data.get("sync_type", "pull")
    records = data.get("records", [])

    if not client_id:
        return jsonify({"error": "client_id required"}), 400

    client = RemoteClient.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404

    # Verify client authentication
    auth_header = request.headers.get("Authorization", "")
    if not client.client_secret or not auth_header.startswith("Bearer ") or auth_header[7:] != client.client_secret:
        return jsonify({"error": "Unauthorized"}), 401

    # Log sync
    sync_log = RemoteSyncLog(
        client_id=client.id,
        company_id=client.company_id,
        sync_type=sync_type,
        direction="to_server",
        records_count=len(records),
        status="success",
    )
    db.session.add(sync_log)

    client.last_sync = datetime.utcnow()
    client.sync_token = data.get("sync_token")

    db.session.commit()

    return jsonify({"ok": True, "sync_id": sync_log.id})


# ── ADMIN ENDPOINTS (called from admin panel) ──────────────

@remote_api_bp.route("/clients", methods=["GET"])
@require_master
def list_clients():
    """List all remote clients."""
    company_id = request.args.get("company_id")
    status = request.args.get("status")

    q = RemoteClient.query
    if company_id:
        q = q.filter_by(company_id=int(company_id))
    if status:
        q = q.filter_by(status=status)

    clients = q.order_by(RemoteClient.last_heartbeat.desc()).all()

    # Mark stale clients (no heartbeat in 5 minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    for c in clients:
        if c.last_heartbeat and c.last_heartbeat < cutoff and c.status == "active":
            c.status = "offline"

    # Expire pending commands older than 24 hours
    cmd_cutoff = datetime.utcnow() - timedelta(hours=24)
    stale_cmds = RemoteCommand.query.filter(
        RemoteCommand.status.in_(["pending", "sent"]),
        RemoteCommand.issued_at < cmd_cutoff,
    ).all()
    for cmd in stale_cmds:
        cmd.status = "failed"
        cmd.result = {"error": "Command expired (no client response)"}

    db.session.commit()

    # Pending-command counts in ONE aggregate query (no per-client N+1)
    from sqlalchemy import func as _func
    _counts = dict(
        db.session.query(
            RemoteCommand.client_id, _func.count(RemoteCommand.id)
        ).filter(
            RemoteCommand.client_id.in_([c.id for c in clients]),
            RemoteCommand.status.in_(["pending", "sent"]),
        ).group_by(RemoteCommand.client_id).all()
    ) if clients else {}

    out = []
    for c in clients:
        d = c.to_dict()
        d["pending_commands_count"] = _counts.get(c.id, 0)
        out.append(d)
    return jsonify(out)


@remote_api_bp.route("/clients/<int:client_db_id>", methods=["GET"])
@require_master
def get_client(client_db_id):
    """Get client details with commands and sync logs."""
    client = db.session.get(RemoteClient, client_db_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    commands = RemoteCommand.query.filter_by(client_id=client.id)\
        .order_by(RemoteCommand.issued_at.desc()).limit(50).all()
    sync_logs = RemoteSyncLog.query.filter_by(client_id=client.id)\
        .order_by(RemoteSyncLog.started_at.desc()).limit(50).all()

    return jsonify({
        "client": client.to_dict(),
        "commands": [c.to_dict() for c in commands],
        "sync_logs": [s.to_dict() for s in sync_logs],
    })


@remote_api_bp.route("/clients/<int:client_db_id>/command", methods=["POST"])
@require_master
def send_command(client_db_id):
    """Send a command to a remote client."""
    client = db.session.get(RemoteClient, client_db_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    command = data.get("command")
    payload = data.get("payload", {})

    if not command:
        return jsonify({"error": "command required"}), 400

    valid_commands = [
        "set_role", "update_modules", "suspend", "reactivate",
        "sync_data", "update_config", "push_permissions",
        "lock", "unlock", "restart", "update_password"
    ]
    if command not in valid_commands:
        return jsonify({"error": f"Invalid command. Valid: {valid_commands}"}), 400

    user = _get_master_user()
    cmd = RemoteCommand(
        client_id=client.id,
        company_id=client.company_id,
        command=command,
        payload=payload,
        status="pending",
        issued_by=user.email if user else "system",
    )
    db.session.add(cmd)
    db.session.commit()

    log.info(f"Command '{command}' queued for client {client.client_id}")

    return jsonify({"ok": True, "command": cmd.to_dict()})


@remote_api_bp.route("/clients/<int:client_db_id>/config", methods=["PUT"])
@require_master
def update_config(client_db_id):
    """Push remote configuration to a client."""
    client = db.session.get(RemoteClient, client_db_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    config = client.remote_config or {}
    config.update(data)
    client.remote_config = config

    # Also queue as a command
    cmd = RemoteCommand(
        client_id=client.id,
        company_id=client.company_id,
        command="update_config",
        payload=data,
        status="pending",
        issued_by=_get_master_user().email if _get_master_user() else "system",
    )
    db.session.add(cmd)
    db.session.commit()

    return jsonify({"ok": True, "remote_config": client.remote_config})


@remote_api_bp.route("/clients/<int:client_db_id>/suspend", methods=["POST"])
@require_master
def suspend_client(client_db_id):
    """Suspend a remote client."""
    client = db.session.get(RemoteClient, client_db_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    client.status = "suspended"
    client.is_authorized = False

    cmd = RemoteCommand(
        client_id=client.id,
        company_id=client.company_id,
        command="lock",
        payload={"reason": "Suspended by admin"},
        status="pending",
        issued_by=_get_master_user().email if _get_master_user() else "system",
    )
    db.session.add(cmd)
    db.session.commit()

    return jsonify({"ok": True})


@remote_api_bp.route("/clients/<int:client_db_id>/reactivate", methods=["POST"])
@require_master
def reactivate_client(client_db_id):
    """Reactivate a suspended client."""
    client = db.session.get(RemoteClient, client_db_id)
    if not client:
        return jsonify({"error": "Not found"}), 404

    client.status = "active"
    client.is_authorized = True

    cmd = RemoteCommand(
        client_id=client.id,
        company_id=client.company_id,
        command="unlock",
        payload={},
        status="pending",
        issued_by=_get_master_user().email if _get_master_user() else "system",
    )
    db.session.add(cmd)
    db.session.commit()

    return jsonify({"ok": True})


@remote_api_bp.route("/broadcast", methods=["POST"])
@require_master
def broadcast_command():
    """Send a command to ALL clients of a company (or all clients)."""
    data = request.get_json(silent=True) or {}
    company_id = data.get("company_id")
    command = data.get("command")
    payload = data.get("payload", {})

    if not command:
        return jsonify({"error": "command required"}), 400

    q = RemoteClient.query.filter_by(status="active")
    if company_id:
        q = q.filter_by(company_id=int(company_id))

    clients = q.all()
    user = _get_master_user()
    count = 0

    for client in clients:
        cmd = RemoteCommand(
            client_id=client.id,
            company_id=client.company_id,
            command=command,
            payload=payload,
            status="pending",
            issued_by=user.email if user else "system",
        )
        db.session.add(cmd)
        count += 1

    db.session.commit()

    return jsonify({"ok": True, "commands_sent": count})


@remote_api_bp.route("/stats", methods=["GET"])
@require_master
def remote_stats():
    """Get remote management statistics."""
    total = RemoteClient.query.count()
    active = RemoteClient.query.filter_by(status="active").count()
    offline = RemoteClient.query.filter_by(status="offline").count()
    suspended = RemoteClient.query.filter_by(status="suspended").count()

    pending_cmds = RemoteCommand.query.filter_by(status="pending").count()
    executed_cmds = RemoteCommand.query.filter_by(status="executed").count()

    return jsonify({
        "total_clients": total,
        "active_clients": active,
        "offline_clients": offline,
        "suspended_clients": suspended,
        "pending_commands": pending_cmds,
        "executed_commands": executed_cmds,
    })
