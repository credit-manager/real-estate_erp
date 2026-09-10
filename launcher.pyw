# -*- coding: utf-8 -*-
"""DynamicPro ERP - Desktop Launcher (Frozen Build)
Runs Flask server in-process and opens a native pywebview window.
No external Python required on the target machine.
"""
import os
import sys
import time
import threading
import socket
import logging

# ── Paths ──
if getattr(sys, "frozen", False):
    BUNDLE_DIR = os.path.dirname(sys.executable)
    APP_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

os.environ.setdefault("DYNAMICPRO_MODE", "production")

_log_dir = os.path.join(os.environ.get("APPDATA", BUNDLE_DIR), "DynamicPro")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "dynamicpro.log")

try:
    from logging.handlers import RotatingFileHandler
    _file_handler = RotatingFileHandler(_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
except Exception:
    _file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("[DynamicPro] %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
log = logging.getLogger("dynamicpro")


def _wait_for_port(port, host="127.0.0.1", timeout=30):
    """Block until the Flask server is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    # ── 1. Import server_config (reads %APPDATA%\DynamicPro\server_config.json) ──
    import server_config
    port = server_config.get_port()

    # Make sure port is not already in use
    if server_config.is_port_in_use(port):
        log.warning(f"Port {port} is already in use. Trying next port...")
        for candidate in range(port + 1, port + 20):
            if not server_config.is_port_in_use(candidate):
                port = candidate
                break

    # ── 2. Start Flask server in a background thread ──
    from app import create_app
    app = create_app()

    def run_server():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # ── 3. Wait for server to be ready ──
    log.info(f"Starting server on port {port}...")
    if not _wait_for_port(port, timeout=30):
        log.error("Server failed to start within 30 seconds.")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Server failed to start within 30 seconds.", "DynamicPro", 0x10)
        except Exception:
            pass
        return

    log.info(f"Server ready at http://127.0.0.1:{port}")

    # ── 3b. Start remote sync agent (optional, for cloud-managed clients) ──
    # Enabled via env: REMOTE_MASTER_URL + REMOTE_COMPANY_ID
    try:
        _master_url = os.environ.get("REMOTE_MASTER_URL", "").strip()
        _company_id = os.environ.get("REMOTE_COMPANY_ID", "").strip()
        if _master_url and _company_id:
            from remote_sync import RemoteSyncAgent
            _agent = RemoteSyncAgent(master_url=_master_url, company_id=int(_company_id), auto_start=True)
            log.info(f"Remote sync agent started for company {_company_id}")
    except Exception as _e:
        log.warning(f"Remote agent not started: {_e}")

    # ── 4. Open pywebview window (native, no browser needed) ──
    try:
        import webview
        from window_theme import apply_light_theme

        window = webview.create_window(
            title="2TO",
            url=f"http://127.0.0.1:{port}",
            width=1400,
            height=900,
            min_size=(1024, 600),
            resizable=True,
            text_select=True,
        )

        def on_loaded():
            try:
                apply_light_theme(window)
            except Exception:
                pass

        window.events.before_loaded += on_loaded
        log.info("Opening window...")
        webview.start(debug=False)

    except ImportError:
        log.warning("pywebview not available, falling back to browser...")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
    except Exception as e:
        log.error(f"Window error: {e}")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
