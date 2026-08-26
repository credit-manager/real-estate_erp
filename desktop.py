"""Dynamic Pro ERP - Desktop Launcher (Live Source Mode).

Runs the Flask server from the SOURCE folder (not from the frozen bundle) in
a child process with the auto-reloader enabled, then opens the application in
a native window. Because the server always loads the current source code:

- Any change to Python files, templates or static files is applied
  automatically (the server restarts itself on change).
- No rebuild of the exe is needed after edits.
- The PDF save dialog also delegates to the live source so reports are always
  built from the latest code.

Modes:
  (default)      open the native window
  --background   run the server only (Windows auto-start, no window)
  --dev          show the server console window (for development)
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
    """مجلد المصدر الذي يُشغَّل منه الخادم (حتى في النسخة المجمعة)."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        marker = os.path.join(exe_dir, "_source_dir.txt")
        if os.path.isfile(marker):
            try:
                with open(marker, encoding="utf-8") as fh:
                    path = fh.read().strip()
                if path and os.path.isdir(path):
                    return path
            except OSError:
                pass
        parent = os.path.abspath(os.path.join(exe_dir, os.pardir))
        if os.path.isfile(os.path.join(parent, "app.py")) and os.path.isdir(os.path.join(parent, "templates")):
            return parent
        return exe_dir
    return os.path.abspath(os.path.dirname(__file__))


ROOT = _root_dir()

# أدلة Python المحتملة على هذا الجهاز (تُفضَّل الإصدارات المثبّت عليها الحزم)
_PYTHON_CANDIDATES = [
    r"C:\Users\MG\AppData\Local\Programs\Python\Python311\pythonw.exe",
    r"C:\Users\MG\AppData\Local\Programs\Python\Python311\python.exe",
    r"C:\Users\MG\AppData\Local\Programs\Python\Python313\pythonw.exe",
    r"C:\Users\MG\AppData\Local\Programs\Python\Python313\python.exe",
    r"C:\Program Files\Python311\pythonw.exe",
    r"C:\Program Files\Python311\python.exe",
    r"C:\Python311\pythonw.exe",
    r"C:\Python311\python.exe",
]


def _find_python(console=False):
    names = ("python", "pythonw") if console else ("pythonw", "python")
    for name in names:
        p = shutil_which(name)
        if p:
            return p
    for cand in _PYTHON_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return None


def shutil_which(name):
    import shutil
    return shutil.which(name)


def _kill_tree(pid):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=10)
    except Exception:  # noqa: BLE001
        pass


def _server_loop(port, console, state, stop_event):
    """يشغّل خادم المصدر (auto-reload) ويعيد تشغيله إن توقف."""
    py = _find_python(console=console)
    if not py:
        raise RuntimeError("لم يتم العثور على Python على هذا الجهاز.")
    while not stop_event.is_set():
        env = os.environ.copy()
        # الوضع: development مع نافذة كونسول --dev، والإنتاج في باقي الحالات
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


def _stop_server(state, stop_event):
    stop_event.set()
    proc = state.get("proc")
    if proc and proc.poll() is None:
        _kill_tree(proc.pid)


def _wait_for_server(port, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _build_pdf_live(doc_type, doc_id, lang):
    """يبني ملف PDF من المصدر المباشر عبر سكربت مساعد."""
    import tempfile
    py = _find_python(console=True)
    script = os.path.join(ROOT, "live_pdf_builder.py")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [py, script, doc_type, str(doc_id), lang, tmp.name],
            cwd=ROOT, timeout=120, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


class JsApi:
    """Python-side API exposed to the webview via window.pywebview.api."""

    def __init__(self, window):
        self._window = window

    def save_pdf(self, doc_type, doc_id, lang="ar"):
        try:
            data = _build_pdf_live(doc_type, int(doc_id), lang)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cancelled": False, "error": str(exc)}

        filename = f"{doc_type}-{doc_id}.pdf"
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=filename, file_types=("PDF files (*.pdf)",)
        )
        if result:
            try:
                path = result[0] if isinstance(result, (tuple, list)) else result
                with open(path, "wb") as fh:
                    fh.write(data)
                return {"ok": True}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "cancelled": False, "error": str(exc)}
        return {"ok": False, "cancelled": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Pro ERP server launcher")
    parser.add_argument("--background", action="store_true", help="start the server without a window")
    parser.add_argument("--dev", action="store_true", help="show the server console (development)")
    args = parser.parse_args()

    port = server_config.get_port()
    webview.settings["ALLOW_DOWNLOADS"] = True

    stop_event = threading.Event()
    state = {"proc": None}
    threading.Thread(target=_server_loop, args=(port, args.dev, state, stop_event), daemon=True).start()

    if args.background:
        while True:
            time.sleep(3600)
    else:
        _wait_for_server(port)
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
        webview.start()
        _stop_server(state, stop_event)
