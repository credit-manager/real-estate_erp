"""Dynamic Pro ERP - Desktop Launcher.

Development mode keeps the live-source workflow. A frozen PyInstaller build is
self-contained: it imports the bundled Flask application in-process instead of
looking for Python.exe and source files on the target computer.
"""
import argparse
import os
import socket
import subprocess
import sys
import threading
import time

import webview

from window_theme import apply_light_titlebar
import server_config

TITLE = "Dynamic Pro ERP"


def _root_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


ROOT = _root_dir()


def _find_python(console=False):
    """Only used by the live-source development launcher."""
    import shutil
    names = ("python", "pythonw") if console else ("pythonw", "python")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _kill_tree(pid):
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        pass


def _bundled_server_loop(port, state, stop_event):
    """Serve the bundled Flask application without spawning Python.exe."""
    from werkzeug.serving import make_server
    from app import app

    server = make_server("127.0.0.1", port, app, threaded=True)
    state["server"] = server
    state["proc"] = None
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        try:
            server.server_close()
        except Exception:  # noqa: BLE001
            pass


def _source_server_loop(port, console, state, stop_event):
    """Development-only source server with the existing auto-restart behavior."""
    py = _find_python(console=console)
    if not py:
        raise RuntimeError("لم يتم العثور على Python على هذا الجهاز في وضع التطوير.")

    while not stop_event.is_set():
        env = os.environ.copy()
        env["DYNAMICPRO_MODE"] = "dev" if console else "production"
        proc = subprocess.Popen(
            [py, os.path.join(ROOT, "app.py")],
            cwd=ROOT,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=None if console else subprocess.DEVNULL,
            stderr=None if console else subprocess.DEVNULL,
        )
        state["proc"] = proc
        proc.wait()
        state["proc"] = None
        if stop_event.is_set():
            break
        _kill_tree(proc.pid)
        time.sleep(2)


def _server_loop(port, console, state, stop_event):
    if getattr(sys, "frozen", False):
        _bundled_server_loop(port, state, stop_event)
    else:
        _source_server_loop(port, console, state, stop_event)


def _stop_server(state, stop_event):
    stop_event.set()
    server = state.get("server")
    if server:
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001
            pass
    proc = state.get("proc")
    if proc and proc.poll() is None:
        _kill_tree(proc.pid)


def _wait_for_server(port, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


class JsApi:
    """Python-side API exposed to the webview via window.pywebview.api."""

    def __init__(self, window):
        self._window = window

    def save_pdf(self, doc_type, doc_id, lang="ar"):
        """Generate a PDF through the application's own code when frozen."""
        try:
            from live_pdf_builder import build_pdf_bytes
            data = build_pdf_bytes(doc_type, int(doc_id), lang)
        except ImportError:
            return {"ok": False, "cancelled": False, "error": "PDF builder is not available in this build."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cancelled": False, "error": str(exc)}

        filename = f"{doc_type}-{doc_id}.pdf"
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=("PDF files (*.pdf)",),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        try:
            path = result[0] if isinstance(result, (tuple, list)) else result
            with open(path, "wb") as fh:
                fh.write(data)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cancelled": False, "error": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Pro ERP desktop launcher")
    parser.add_argument("--background", action="store_true", help="start the server without a window")
    parser.add_argument("--dev", action="store_true", help="use the live source development server")
    args = parser.parse_args()

    # The frozen application always uses the bundled/local desktop mode.
    if getattr(sys, "frozen", False):
        os.environ["DYNAMICPRO_MODE"] = "production"
        os.environ["DYNAMICPRO_DESKTOP"] = "1"

    port = server_config.get_port()
    webview.settings["ALLOW_DOWNLOADS"] = True

    stop_event = threading.Event()
    state = {"proc": None, "server": None}
    thread = threading.Thread(
        target=_server_loop,
        args=(port, args.dev, state, stop_event),
        daemon=True,
        name="dynamicpro-server",
    )
    thread.start()

    if args.background:
        try:
            while not stop_event.is_set():
                time.sleep(3600)
        finally:
            _stop_server(state, stop_event)
    else:
        if not _wait_for_server(port):
            _stop_server(state, stop_event)
            raise RuntimeError(f"لم يبدأ خادم Dynamic Pro على المنفذ {port}.")

        window = webview.create_window(
            TITLE,
            f"http://127.0.0.1:{port}",
            width=1280,
            height=800,
            min_size=(960, 620),
        )
        api = JsApi(window)
        window.expose(api.save_pdf)
        apply_light_titlebar(window)
        try:
            webview.start()
        finally:
            _stop_server(state, stop_event)
