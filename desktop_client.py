"""Dynamic Pro ERP - Desktop Client.

Connects to a Dynamic Pro server running on the local network and shows the
application in a native window. On first run it asks for the server address
and stores it in %APPDATA%\\DynamicPro\\client_config.json.

No Python, PostgreSQL or project files are required on client machines.
"""
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
from urllib.request import urlopen

import webview

from window_theme import apply_light_titlebar

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DynamicPro")
CONFIG_FILE = os.path.join(CONFIG_DIR, "client_config.json")
TITLE = "Dynamic Pro ERP"


def _load_url():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("url", "")
    except Exception:
        return ""


def _save_url(url):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump({"url": url}, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _ask_url():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    url = simpledialog.askstring(
        TITLE,
        "أدخل عنوان خادم Dynamic Pro\nمثال: http://192.168.1.10:5000",
        parent=root,
        initialvalue=_load_url() or "http://localhost:5000",
    )
    root.destroy()
    if not url:
        return None
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    if url:
        _save_url(url)
    return url or None


def _reachable(url, timeout=4):
    try:
        resp = urlopen(url + "/login", timeout=timeout)
        return resp.status < 500
    except Exception:
        return False


if __name__ == "__main__":
    url = _load_url() or _ask_url()
    if not url:
        raise SystemExit("لم يتم إدخال عنوان الخادم.")

    if not _reachable(url):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        answer = messagebox.askyesno(
            TITLE,
            f"تعذر الوصول إلى الخادم:\n{url}\n\n"
            "تأكد أن جهاز الخادم يعمل وأنك على نفس الشبكة.\n"
            "هل تريد تغيير العنوان والمحاولة مجددًا؟",
        )
        root.destroy()
        if answer:
            new_url = _ask_url()
            if not new_url:
                raise SystemExit("تم الإلغاء.")
            url = new_url

    window = webview.create_window(TITLE, url, width=1280, height=800, min_size=(960, 620))
    apply_light_titlebar(window)
    webview.start()
