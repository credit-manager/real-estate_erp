# -*- coding: utf-8 -*-
"""Remote Sync Agent for Desktop/Laptop Clients.

Runs in the background on offline clients to:
1. Send periodic heartbeats to the master server
2. Execute commands pushed from the admin panel
3. Sync data between local SQLite and master server

Usage:
    from remote_sync import RemoteSyncAgent
    agent = RemoteSyncAgent(master_url="http://your-server:1000", company_id=1)
    agent.start()  # Starts background thread
"""
import json
import logging
import os
import platform
import socket
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)


def _get_machine_id():
    """Generate a unique machine identifier."""
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography")
            machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
            return f"DP-{machine_guid[:16].upper()}"
        elif platform.system() == "Linux":
            with open("/etc/machine-id") as f:
                return f"DP-{f.read().strip()[:16].upper()}"
    except Exception:
        pass
    hostname = socket.gethostname()
    return f"DP-{hostname[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"


def _get_local_ip():
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_mac_address():
    """Get the MAC address of the primary network interface."""
    mac = uuid.getnode()
    return ':'.join(f'{(mac >> (8 * i)) & 0xFF:02X}' for i in reversed(range(6)))


def _get_data_dir():
    """Get the persistent data directory for the agent."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    d = Path(base) / "DynamicPro"
    d.mkdir(parents=True, exist_ok=True)
    return d


class RemoteSyncAgent:
    """Background agent that keeps the client connected to the master server."""

    def __init__(self, master_url, company_id, client_name=None,
                 heartbeat_interval=60, auto_start=False):
        self.master_url = master_url.rstrip("/")
        self.company_id = company_id
        self.client_id = _get_machine_id()
        self.client_name = client_name or socket.gethostname()
        self.heartbeat_interval = heartbeat_interval

        self._running = False
        self._thread = None
        self._config = {}
        self._command_handlers = {}
        self._client_secret = None

        # Persistent data paths
        self._data_dir = _get_data_dir()
        self._secret_file = self._data_dir / "remote_secret.json"
        self._lock_file = self._data_dir / "remote_lock.json"
        self._inbox_dir = self._data_dir / "sync_inbox"
        self._inbox_dir.mkdir(parents=True, exist_ok=True)

        # Suspended backoff (server 403): poll rarely until reactivated
        self._backoff_until = 0.0
        self._backoff_interval = 600

        # Load persisted state
        self._load_secret()
        self._load_lock_state()

        # Register default command handlers
        self.register_handler("update_config", self._handle_update_config)
        self.register_handler("lock", self._handle_lock)
        self.register_handler("unlock", self._handle_unlock)
        self.register_handler("restart", self._handle_restart)
        self.register_handler("sync_data", self._handle_sync_data)

        if auto_start:
            self.start()

    # ── Persistence ──────────────────────────────────────────

    def _load_secret(self):
        """Load client_secret from disk if available."""
        try:
            if self._secret_file.exists():
                data = json.loads(self._secret_file.read_text(encoding="utf-8"))
                self._client_secret = data.get("client_secret")
        except Exception:
            pass

    def _save_secret(self, secret):
        """Save client_secret to disk."""
        try:
            self._secret_file.write_text(
                json.dumps({"client_secret": secret, "client_id": self.client_id}),
                encoding="utf-8"
            )
            self._client_secret = secret
        except Exception as e:
            log.error(f"Failed to save client_secret: {e}")

    def _load_lock_state(self):
        """Load lock state from disk."""
        try:
            if self._lock_file.exists():
                data = json.loads(self._lock_file.read_text(encoding="utf-8"))
                self._config["locked"] = data.get("locked", False)
                self._config["lock_reason"] = data.get("lock_reason", "")
        except Exception:
            pass

    def _save_lock_state(self):
        """Persist lock state to disk."""
        try:
            self._lock_file.write_text(
                json.dumps({
                    "locked": self._config.get("locked", False),
                    "lock_reason": self._config.get("lock_reason", ""),
                }),
                encoding="utf-8"
            )
        except Exception as e:
            log.error(f"Failed to save lock state: {e}")

    # ── Auth Headers ─────────────────────────────────────────

    def _auth_headers(self):
        """Return Authorization headers for server requests."""
        headers = {"Content-Type": "application/json"}
        if self._client_secret:
            headers["Authorization"] = f"Bearer {self._client_secret}"
        return headers

    # ── Lifecycle ────────────────────────────────────────────

    def register_handler(self, command, handler):
        """Register a handler for a specific command type."""
        self._command_handlers[command] = handler

    def start(self):
        """Start the background heartbeat thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info(f"Remote sync agent started for {self.client_id}")

    def stop(self):
        """Stop the heartbeat thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Remote sync agent stopped")

    def _run_loop(self):
        """Main loop: heartbeat + execute commands."""
        while self._running:
            try:
                now = time.time()
                if now >= self._backoff_until:
                    self._heartbeat()
                else:
                    time.sleep(min(30, self._backoff_until - now))
                    continue
            except Exception as e:
                log.error(f"Heartbeat failed: {e}")
            time.sleep(self.heartbeat_interval)

    # ── Heartbeat ────────────────────────────────────────────

    def _heartbeat(self):
        """Send heartbeat and process any pending commands."""
        payload = {
            "client_id": self.client_id,
            "company_id": self.company_id,
            "client_name": self.client_name,
            "client_type": "desktop",
            "os_info": f"{platform.system()} {platform.release()}",
            "app_version": getattr(self, "app_version", "1.0.0"),
            "local_ip": _get_local_ip(),
            "mac_address": _get_mac_address(),
        }

        resp = requests.post(
            f"{self.master_url}/api/remote/heartbeat",
            json=payload,
            headers=self._auth_headers(),
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            # (Re)activated or healthy: clear any suspend backoff
            self._backoff_until = 0.0
            # First-time registration: store the returned secret
            if data.get("client_secret"):
                self._save_secret(data["client_secret"])
                log.info("Client registered, secret stored locally")
            # Update local config from server
            if data.get("remote_config"):
                self._config.update(data["remote_config"])
                self._save_lock_state()
            # Execute pending commands
            for cmd in data.get("pending_commands", []):
                self._execute_command(cmd)
        elif resp.status_code == 401:
            log.warning("Authentication failed - clearing stored secret")
            self._client_secret = None
            if self._secret_file.exists():
                self._secret_file.unlink()
        elif resp.status_code == 403:
            # Suspended by admin: back off polling until reactivated.
            # The 200 path below clears the backoff automatically.
            self._backoff_until = time.time() + self._backoff_interval
            log.warning(
                f"Client suspended by server; backing off for {self._backoff_interval}s")
        else:
            log.warning(f"Heartbeat returned {resp.status_code}")

    def _execute_command(self, cmd):
        """Execute a command received from the server."""
        cmd_id = cmd.get("id")
        command = cmd.get("command")
        payload = cmd.get("payload", {})

        log.info(f"Executing command: {command} (id={cmd_id})")

        handler = self._command_handlers.get(command)
        result = {"status": "executed"}

        if handler:
            try:
                handler(payload)
            except Exception as e:
                result = {"status": "failed", "error": str(e)}
                log.error(f"Command {command} failed: {e}")
        else:
            result = {"status": "failed", "error": f"Unknown command: {command}"}

        # Report result back to server
        try:
            requests.post(
                f"{self.master_url}/api/remote/command-result",
                json={"command_id": cmd_id, **result},
                headers=self._auth_headers(),
                timeout=10,
            )
        except Exception as e:
            log.error(f"Failed to report command result: {e}")

    # ── Default Command Handlers ────────────────────────────

    def _handle_update_config(self, payload):
        """Update local configuration from server."""
        self._config.update(payload)
        log.info(f"Config updated: {list(payload.keys())}")

    def _handle_lock(self, payload):
        """Lock the client (disable access)."""
        self._config["locked"] = True
        self._config["lock_reason"] = payload.get("reason", "Locked by admin")
        self._save_lock_state()
        log.warning(f"Client locked: {payload.get('reason')}")

    def _handle_unlock(self, payload):
        """Unlock the client."""
        self._config["locked"] = False
        self._config.pop("lock_reason", None)
        self._save_lock_state()
        log.info("Client unlocked")

    def _handle_restart(self, payload):
        """Restart the application."""
        import sys
        log.info("Restarting application...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _handle_sync_data(self, payload):
        """Persist server-pushed records to the local sync inbox.

        The host application consumes them via drain_inbox()/ack_inbox().
        Register a custom handler for fully custom logic.
        """
        records = payload.get("records", []) if isinstance(payload, dict) else []
        cmd_tag = str(payload.get("batch_id") or int(time.time())) if isinstance(payload, dict) else str(int(time.time()))
        safe_tag = "".join(c for c in cmd_tag if c.isalnum() or c in "-_")[:40] or "batch"
        try:
            path = self._inbox_dir / f"{safe_tag}.json"
            path.write_text(json.dumps({
                "received_at": datetime.utcnow().isoformat(),
                "records": records,
            }, ensure_ascii=False), encoding="utf-8")
            log.info(f"Sync batch stored in inbox: {path.name} ({len(records)} records)")
            self._prune_inbox()
        except Exception as e:
            log.error(f"Failed to store sync batch: {e}")
            raise

    def _prune_inbox(self, keep=100):
        """Keep only the newest inbox files (disk safety)."""
        try:
            files = sorted(self._inbox_dir.glob("*.json"),
                           key=lambda p: p.stat().st_mtime)
            for stale in files[:-keep]:
                stale.unlink()
        except Exception:
            pass

    def drain_inbox(self):
        """Yield (filename, payload) for each pending inbox batch, oldest first."""
        try:
            files = sorted(self._inbox_dir.glob("*.json"),
                           key=lambda p: p.stat().st_mtime)
        except Exception:
            return
        for path in files:
            try:
                yield path.name, json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                log.error(f"Unreadable inbox file {path.name}: {e}")

    def ack_inbox(self, filename):
        """Remove an inbox batch after the application applied it."""
        try:
            target = self._inbox_dir / filename
            if target.parent == self._inbox_dir and target.suffix == ".json":
                target.unlink()
                return True
        except Exception as e:
            log.error(f"Failed to ack inbox file {filename}: {e}")
        return False

    # ── Public API ───────────────────────────────────────────

    def get_config(self, key=None, default=None):
        """Get configuration value(s)."""
        if key:
            return self._config.get(key, default)
        return dict(self._config)

    def is_locked(self):
        """Check if the client is locked."""
        return self._config.get("locked", False)

    def send_sync(self, sync_type, records):
        """Send sync data to the server."""
        try:
            resp = requests.post(
                f"{self.master_url}/api/remote/sync",
                json={
                    "client_id": self.client_id,
                    "company_id": self.company_id,
                    "sync_type": sync_type,
                    "records": records,
                    "sync_token": datetime.utcnow().isoformat(),
                },
                headers=self._auth_headers(),
                timeout=30,
            )
            return resp.status_code == 200
        except Exception as e:
            log.error(f"Sync failed: {e}")
            return False
