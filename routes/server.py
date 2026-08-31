"""Server configuration routes (server machine only).

Accessible only from localhost (the server's own desktop app). Provides the
settings page plus JSON endpoints used by it.
"""
import os
import subprocess
import sys

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)

import server_config
from permissions import require_page, require_api

server_bp = Blueprint("server", __name__)

LOCAL_HOSTS = ("127.0.0.1", "::1")


def _is_local():
    return request.remote_addr in LOCAL_HOSTS


def _local_only(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _is_local():
            return jsonify({"success": False, "message": "local-only"}), 403
        return f(*args, **kwargs)

    return wrapper


@server_bp.route("/api/server-info")
def server_info():
    """Public endpoint used by the login page to show the access-password field."""
    return jsonify({
        "access_password_required": bool(current_app.config.get("SERVER_ACCESS_PASSWORD", "")),
        "server_name": "Dynamic Pro ERP",
    })


@server_bp.route("/server-settings")
@require_page("settings")
def settings_page():
    if not _is_local():
        return render_template("server_settings.html", local_only=True)
    return render_template("server_settings.html", local_only=False)


@server_bp.route("/api/server-settings", methods=["GET"])
@require_api("settings", "view")
def get_settings():
    cfg = server_config.load_config()
    stored = cfg.get("access_password", "")
    gemini_key = cfg.get("gemini_api_key", "")
    providers = cfg.get("ai_providers") or {}
    # Mask API keys for security — only return whether each is set
    safe_providers = {}
    for pname, pcfg in providers.items():
        safe_providers[pname] = {
            "enabled": pcfg.get("enabled", False),
            "api_key_set": bool((pcfg.get("api_key") or "").strip()),
            "model": pcfg.get("model", ""),
            "priority": pcfg.get("priority", 99),
        }
    return jsonify({
        "success": True,
        "port": cfg["port"],
        "access_password": "",
        "access_password_set": bool(stored),
        "auto_start": server_config.is_auto_start_enabled(),
        "network_addresses": server_config.get_network_addresses(),
        "frozen": getattr(sys, "frozen", False),
        "gemini_api_key_set": bool(gemini_key),
        "gemini_model": cfg.get("gemini_model", "gemini-2.0-flash"),
        "ai_providers": safe_providers,
    })


@server_bp.route("/api/server-settings", methods=["POST"])
@require_api("settings", "edit")
def save_settings():
    data = request.get_json(silent=True) or {}
    cfg = server_config.load_config()

    if "port" in data:
        try:
            new_port = int(data["port"])
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "invalid-port"}), 400
        if not (1024 <= new_port <= 65535):
            return jsonify({"success": False, "message": "invalid-port"}), 400
        cfg["port"] = new_port

    if "access_password" in data:
        val = str(data["access_password"] or "").strip()
        if val:
            cfg["access_password"] = server_config.hash_access_password(val)
        elif data.get("clear_access_password"):
            cfg["access_password"] = ""

    if "auto_start" in data:
        cfg["auto_start"] = bool(data["auto_start"])
        server_config.set_auto_start(cfg["auto_start"])

    # Legacy gemini fields
    if "gemini_api_key" in data:
        val = str(data["gemini_api_key"] or "").strip()
        cfg["gemini_api_key"] = val

    if "gemini_model" in data:
        cfg["gemini_model"] = str(data["gemini_model"] or "gemini-2.0-flash").strip()

    # Multi-provider AI settings
    if "ai_providers" in data and isinstance(data["ai_providers"], dict):
        providers = cfg.get("ai_providers") or {}
        for pname, pcfg in data["ai_providers"].items():
            if not isinstance(pcfg, dict):
                continue
            if pname not in providers:
                providers[pname] = {"enabled": False, "api_key": "", "model": "", "priority": 99}
            if "enabled" in pcfg:
                providers[pname]["enabled"] = bool(pcfg["enabled"])
            if "model" in pcfg:
                providers[pname]["model"] = str(pcfg["model"]).strip()
            if "priority" in pcfg:
                try:
                    providers[pname]["priority"] = int(pcfg["priority"])
                except (TypeError, ValueError):
                    pass
            # Only update api_key if a non-empty value is provided (don't clear by accident)
            if "api_key" in pcfg:
                new_key = str(pcfg["api_key"] or "").strip()
                if new_key:
                    providers[pname]["api_key"] = new_key
                elif pcfg.get("clear_api_key"):
                    providers[pname]["api_key"] = ""
        cfg["ai_providers"] = providers

    ok = server_config.save_config(cfg)
    if not ok:
        return jsonify({"success": False, "message": "write-error"}), 500

    current_app.config["SERVER_ACCESS_PASSWORD"] = cfg["access_password"]

    return jsonify({
        "success": True,
        "port_changed": cfg["port"] != current_app.config.get("SERVER_PORT"),
        "message": "saved",
    })


@server_bp.route("/api/server-restart", methods=["POST"])
@_local_only
@require_api("settings", "edit")
def restart():
    try:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop.py")
            subprocess.Popen([sys.executable, script])
        os._exit(0)
    except Exception:
        return jsonify({"success": False, "message": "restart-failed"}), 500
    return jsonify({"success": True})


@server_bp.route("/api/ai-provider-test", methods=["POST"])
@require_api("settings", "edit")
def test_ai_provider():
    """Test a single AI provider with a simple question."""
    from ai_engine import test_provider
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    model = (data.get("model") or "").strip()
    if not name or not api_key or not model:
        return jsonify({"success": False, "message": "missing-params"}), 400
    result = test_provider(name, api_key, model)
    return jsonify(result)


@server_bp.route("/api/factory-reset/preview", methods=["POST"])
@require_api("settings", "edit")
def factory_reset_preview():
    from factory_reset import get_reset_preview
    preview = get_reset_preview()
    return jsonify({"success": True, "preview": preview})


@server_bp.route("/api/factory-reset", methods=["POST"])
@require_api("settings", "edit")
def factory_reset():
    from factory_reset import factory_reset as do_reset
    data = request.get_json(silent=True) or {}
    confirm = (data.get("confirm") or "").strip()
    if confirm != "RESET":
        return jsonify({"success": False, "message": "اكتب RESET للتأكيد"}), 400
    seed_demo = data.get("seed_demo", False)
    result = do_reset(seed_demo=seed_demo)
    return jsonify(result)
