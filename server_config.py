"""Server configuration for the Dynamic Pro ERP desktop launcher.

Settings are stored in %APPDATA%\\DynamicPro\\server_config.json:
- port:          TCP port the Flask server listens on (default 5000)
- access_password: master password required to log in ("" = disabled)
- auto_start:    whether the server starts automatically with Windows
"""
import json
import os
import socket
import sys
import winreg

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DynamicPro")
CONFIG_FILE = os.path.join(CONFIG_DIR, "server_config.json")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DynamicProServer"

DEFAULTS = {
    "port": 5000,
    "access_password": "",
    "auto_start": False,
    "https_enabled": False,
    "https_port": 5443,
    "gemini_api_key": "",
    "gemini_model": "gemini-2.0-flash",
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh) or {}
        for key in DEFAULTS:
            if key in saved:
                cfg[key] = saved[key]
        cfg["port"] = int(cfg.get("port", 5000)) or 5000
    except Exception:
        pass
    return cfg


def save_config(cfg):
    merged = dict(DEFAULTS)
    merged.update(cfg or {})
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_port():
    return load_config().get("port", 5000)


def get_https_port():
    cfg = load_config()
    try:
        return int(cfg.get("https_port", 5443)) or 5443
    except (TypeError, ValueError):
        return 5443


def is_https_enabled():
    return bool(load_config().get("https_enabled", False))


def get_cert_paths():
    """Returns (cert_pem, key_pem) if both exist, else (None, None)."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
    cert = os.path.join(base, "cert.pem")
    key = os.path.join(base, "key.pem")
    if os.path.isfile(cert) and os.path.isfile(key):
        return cert, key
    return None, None


def get_access_password():
    return load_config().get("access_password", "")


def hash_access_password(plain):
    """يُعيد تمثيلاً غير قابل للقراءة (hash) لكلمة مرور الوصول للخادم."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(str(plain or ""))


def check_access_password(stored, plain):
    """يتحقق من كلمة مرور الوصول مقابل القيمة المخزنة.
    يدعم القيم الجديدة (hash) والقيم القديمة (نص صريح) للتوافق الخلفي."""
    import hmac
    stored = str(stored or "")
    plain = str(plain or "")
    if not stored:
        return not plain
    # hash من werkzeug يحتوي دائماً على ':' (مثل pbkdf2:sha256:... / scrypt:...)
    if ":" in stored and len(stored) > 30:
        from werkzeug.security import check_password_hash
        try:
            return check_password_hash(stored, plain)
        except ValueError:
            return False
    # قيم قديمة مخزنة كنص صريح
    return hmac.compare_digest(stored, plain)


def _launch_command():
    """Command line used to start the server (for the Run registry entry)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop.py")
    return f'"{sys.executable}" "{script}" --background'


def set_auto_start(enabled):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
    except OSError:
        return False
    try:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
        return True
    except OSError:
        return False
    finally:
        try:
            winreg.CloseKey(key)
        except OSError:
            pass


def is_auto_start_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(key, RUN_VALUE)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def get_network_addresses():
    """IPv4 addresses the server can be reached at on the local network."""
    addresses = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
    except Exception:
        pass
    if not addresses:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            addresses.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    return sorted(addresses)


def is_port_in_use(port, host="127.0.0.1"):
    try:
        s = socket.create_connection((host, port), timeout=1.0)
        s.close()
        return True
    except OSError:
        return False
