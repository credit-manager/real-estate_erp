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

logging.basicConfig(level=logging.INFO, format="[DynamicPro] %(message)s")
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
        input("Press Enter to exit...")
        return

    log.info(f"Server ready at http://127.0.0.1:{port}")

    # ── 4. Open pywebview window (native, no browser needed) ──
    try:
        import webview
        from window_theme import apply_light_theme

        window = webview.create_window(
            title="Dynamic Pro ERP",
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
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    except Exception as e:
        log.error(f"Window error: {e}")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
