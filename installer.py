"""Dynamic Pro ERP - self-contained Windows installer."""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import winreg
from tkinter import filedialog, messagebox, ttk

from webview2_runtime import WEBVIEW2_INSTALLER, install_if_missing, installer_path

APP_NAME = "Dynamic Pro ERP"
APP_VERSION = "1.0.0"
SERVER_EXE = "DynamicPro.exe"
INSTALL_SUBDIR = "Dynamic Pro ERP"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DynamicProServer"

PRIMARY = "#1d4ed8"
PRIMARY_DARK = "#1e40af"
BG = "#f3f4f6"
CARD = "#ffffff"
TEXT = "#111827"
MUTED = "#6b7280"
GREEN = "#047857"
AMBER = "#b45309"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def default_source_dir():
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")


def find_server(folder):
    path = os.path.join(folder, SERVER_EXE)
    return path if os.path.isfile(path) else None


def desktop_dir():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
            value = os.path.expandvars(value)
            if os.path.isdir(value):
                return value
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def start_menu_dir():
    base = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "Microsoft", "Windows", "Start Menu", "Programs",
    )
    return os.path.join(base, APP_NAME)


def make_shortcut(lnk_path, target, icon=None, args=""):
    """Create a Windows .lnk using the Windows scripting host COM object."""
    if icon is None:
        icon = target
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath='%s';$s.Arguments='%s';$s.IconLocation='%s,0';"
        "$s.WorkingDirectory='%s';$s.Save()"
        % tuple(
            value.replace("'", "''")
            for value in (lnk_path, target, args, icon, os.path.dirname(target))
        )
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def enable_autostart(exe_path):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, '"%s" --background' % exe_path)


def disable_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except OSError:
        pass


def is_running(exe_name):
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % exe_name],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return exe_name.lower() in result.stdout.lower()


def taskkill(exe_name):
    subprocess.run(
        ["taskkill", "/IM", exe_name, "/F"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def run_smoke_test():
    """Validate that the frozen setup contains the ERP and offline WebView2 payload."""
    if not is_frozen():
        raise RuntimeError("Setup smoke test must run from a PyInstaller executable.")
    bundled = find_server(default_source_dir())
    if not bundled:
        raise RuntimeError("Embedded DynamicPro.exe is missing from the setup bundle.")
    if os.path.getsize(bundled) < 1024 * 1024:
        raise RuntimeError("Embedded DynamicPro.exe is unexpectedly small.")
    runtime = installer_path(default_source_dir())
    if not runtime:
        raise RuntimeError("Embedded WebView2 Offline Runtime installer is missing from the setup bundle.")
    if os.path.getsize(runtime) < 10 * 1024 * 1024:
        raise RuntimeError("Embedded WebView2 Runtime installer is unexpectedly small.")
    print("DYNAMICPRO SETUP SMOKE TEST: PASS", flush=True)


def run_install_smoke_test():
    """Exercise the real payload installation copy path without GUI or shortcuts."""
    if not is_frozen():
        raise RuntimeError("Installer installation smoke test must run from a PyInstaller executable.")
    source = find_server(default_source_dir())
    runtime = installer_path(default_source_dir())
    if not source:
        raise RuntimeError("Embedded DynamicPro.exe is missing from the setup bundle.")
    if not runtime:
        raise RuntimeError("Embedded WebView2 Offline Runtime installer is missing from the setup bundle.")

    temp_root = tempfile.mkdtemp(prefix="dynamicpro-install-smoke-")
    try:
        target = os.path.join(temp_root, INSTALL_SUBDIR)
        os.makedirs(target, exist_ok=True)
        destination = os.path.join(target, SERVER_EXE)
        runtime_destination = os.path.join(target, WEBVIEW2_INSTALLER)
        shutil.copy2(source, destination)
        shutil.copy2(runtime, runtime_destination)
        if not os.path.isfile(destination) or not os.path.isfile(runtime_destination):
            raise RuntimeError("Installed setup payload is incomplete.")
        if os.path.getsize(source) != os.path.getsize(destination) or os.path.getsize(destination) < 1024 * 1024:
            raise RuntimeError("Installed DynamicPro.exe failed integrity/size validation.")
        if os.path.getsize(runtime) != os.path.getsize(runtime_destination) or os.path.getsize(runtime_destination) < 10 * 1024 * 1024:
            raise RuntimeError("Installed WebView2 Runtime payload failed integrity/size validation.")
        print("DYNAMICPRO INSTALL SMOKE TEST: PASS", flush=True)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dynamic Pro ERP - Setup")
        self.geometry("680x590")
        self.minsize(660, 570)
        self.resizable(False, False)
        self.configure(bg=BG)
        try:
            self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.target = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "Programs", INSTALL_SUBDIR,
        )
        self.source = default_source_dir()
        self.server_source = find_server(self.source)
        self.src_var = tk.StringVar(value="Embedded application" if is_frozen() else self.source)
        self.dst_var = tk.StringVar(value=self.target)
        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass
        self._style.configure("TProgressbar", troughcolor="#e5e7eb", background=PRIMARY, borderwidth=0, thickness=10)
        self._build_welcome()

    def _header(self, parent):
        header = tk.Frame(parent, bg=PRIMARY, height=96)
        header.pack(fill="x")
        header.pack_propagate(False)
        inner = tk.Frame(header, bg=PRIMARY)
        inner.pack(fill="both", expand=True, padx=28, pady=18)
        tk.Label(inner, text="DP", bg="#3b82f6", fg="white", font=("Segoe UI", 20, "bold"), width=4, height=2).pack(side="left", padx=(0, 16))
        text = tk.Frame(inner, bg=PRIMARY)
        text.pack(side="left", fill="both", expand=True)
        tk.Label(text, text=APP_NAME, bg=PRIMARY, fg="white", font=("Segoe UI", 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(text, text="Self-contained Windows installer", bg=PRIMARY, fg="#bfdbfe", font=("Segoe UI", 10), anchor="w").pack(fill="x")
        tk.Label(header, text="v" + APP_VERSION, bg=PRIMARY_DARK, fg="#93c5fd", font=("Segoe UI", 9, "bold"), padx=10, pady=4).place(relx=1.0, rely=0.0, x=-14, y=10, anchor="ne")

    def _card(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=24, pady=20)
        card.pack(fill="both", expand=True, padx=24, pady=(18, 10))
        return card

    def _field_label(self, parent, text):
        tk.Label(parent, text=text, bg=CARD, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 4))

    def _path_row(self, parent, variable, browse_cmd=None):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, 14))
        tk.Entry(row, textvariable=variable, font=("Segoe UI", 10), bg="#f9fafb", fg=TEXT, relief="solid", bd=1, state="readonly").pack(side="left", fill="x", expand=True, ipady=6)
        if browse_cmd:
            tk.Button(row, text="Browse...", font=("Segoe UI", 10), bg="#f3f4f6", fg=TEXT, relief="solid", bd=1, padx=14, command=browse_cmd).pack(side="left", padx=(8, 0), ipady=3)

    def _primary_btn(self, parent, text, command, state="normal"):
        button = tk.Button(parent, text=text, font=("Segoe UI", 11, "bold"), bg=PRIMARY, fg="white", padx=26, pady=6, relief="flat", activebackground=PRIMARY_DARK, command=command)
        button.config(state=state)
        button.pack(side="left")
        return button

    def _build_welcome(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._header(self)
        card = self._card(self)
        self._field_label(card, "Application package")
        self._path_row(card, self.src_var, self._browse_source if not is_frozen() else None)
        self._field_label(card, "Installation folder")
        self._path_row(card, self.dst_var, self._browse_dest)
        options = tk.Frame(card, bg=CARD)
        options.pack(fill="x", pady=(0, 14))
        self.opt_desktop = tk.BooleanVar(value=True)
        self.opt_startmenu = tk.BooleanVar(value=True)
        self.opt_autostart = tk.BooleanVar(value=True)
        for variable, label in (
            (self.opt_desktop, "Create Desktop shortcut"),
            (self.opt_startmenu, "Add to Start Menu"),
            (self.opt_autostart, "Start the ERP automatically with Windows"),
        ):
            tk.Checkbutton(options, text=label, variable=variable, bg=CARD, fg=TEXT, font=("Segoe UI", 10), activebackground=CARD, selectcolor="#e0e7ff", anchor="w").pack(fill="x", pady=2)
        tk.Frame(card, bg="#e5e7eb", height=1).pack(fill="x", pady=(0, 14))
        info = tk.Frame(card, bg="#eff6ff", padx=14, pady=10)
        info.pack(fill="x")
        tk.Label(info, text="Included in this setup", bg="#eff6ff", fg=PRIMARY_DARK, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        for text in (
            "  - Dynamic Pro ERP desktop application (embedded)",
            "  - Microsoft Edge WebView2 Evergreen Offline Runtime (embedded)",
            "  - Local SQLite data directory and first-run configuration",
            "  - No Python, PostgreSQL, Git, or project source files required",
        ):
            tk.Label(info, text=text, bg="#eff6ff", fg=TEXT, font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.status = tk.Label(card, text="", bg=CARD, fg=GREEN, font=("Segoe UI", 10), anchor="w", wraplength=580)
        self.status.pack(fill="x", pady=(12, 8))
        self.progress = ttk.Progressbar(card, style="TProgressbar", maximum=100)
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.pack_forget()
        footer = tk.Frame(self, bg=BG, padx=24, pady=16)
        footer.pack(fill="x")
        self.install_btn = self._primary_btn(footer, "Install", self._install)
        tk.Button(footer, text="Cancel", font=("Segoe UI", 10), bg=BG, fg=TEXT, padx=18, pady=6, relief="flat", command=self.destroy).pack(side="left")
        self._refresh_status()

    def _browse_source(self):
        folder = filedialog.askdirectory(initialdir=self.source, title="Select dist folder")
        if folder:
            self.source = folder
            self.src_var.set(folder)
            self._refresh_status()

    def _browse_dest(self):
        folder = filedialog.askdirectory(initialdir=self.dst_var.get(), title="Select installation folder")
        if folder:
            self.dst_var.set(folder)

    def _refresh_status(self):
        self.server_source = find_server(self.source)
        runtime = installer_path(self.source)
        if self.server_source and runtime:
            self.status.config(text="Ready to install. ERP and offline WebView2 Runtime are included.", fg=GREEN)
            self.install_btn.config(state="normal")
        elif not self.server_source:
            self.status.config(text="DynamicPro.exe was not found. Build the desktop application first.", fg=AMBER)
            self.install_btn.config(state="disabled")
        else:
            self.status.config(text="WebView2 Offline Runtime was not found in the setup package.", fg=AMBER)
            self.install_btn.config(state="disabled")

    def _install(self):
        self.target = self.dst_var.get().strip()
        self.server_source = find_server(self.source)
        if not self.server_source or not installer_path(self.source):
            self._refresh_status()
            return
        if is_running(SERVER_EXE):
            if not messagebox.askyesno("Application in use", "Dynamic Pro ERP is running and will be closed.\n\nContinue?"):
                return
            taskkill(SERVER_EXE)
        self.install_btn.config(state="disabled", text="Installing...")
        self.progress.pack(fill="x", pady=(0, 4))
        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self):
        def status(message, percent):
            self.after(0, lambda: self.status.config(text=message, fg=PRIMARY_DARK))
            self.after(0, lambda: self.progress.config(value=percent))
        try:
            status("Preparing installation folder...", 10)
            os.makedirs(self.target, exist_ok=True)
            status("Installing Microsoft Edge WebView2 Runtime...", 25)
            install_if_missing(default_source_dir())
            destination = os.path.join(self.target, SERVER_EXE)
            status("Copying Dynamic Pro ERP...", 45)
            for _ in range(3):
                try:
                    shutil.copy2(self.server_source, destination)
                    break
                except PermissionError:
                    taskkill(SERVER_EXE)
                    time.sleep(1)
            else:
                raise RuntimeError("Could not replace DynamicPro.exe because it is in use.")
            if self.opt_desktop.get():
                status("Creating Desktop shortcut...", 65)
                make_shortcut(os.path.join(desktop_dir(), "Dynamic Pro ERP.lnk"), destination)
            if self.opt_startmenu.get():
                status("Creating Start Menu shortcut...", 75)
                menu = start_menu_dir()
                os.makedirs(menu, exist_ok=True)
                make_shortcut(os.path.join(menu, "Dynamic Pro ERP.lnk"), destination)
                self._write_uninstaller()
            if self.opt_autostart.get():
                status("Enabling automatic startup...", 88)
                enable_autostart(destination)
            else:
                disable_autostart()
            status("Installation complete.", 100)
            self.after(250, self._show_done)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Installation failed", str(exc)))
            self.after(0, lambda: self.install_btn.config(state="normal", text="Install"))

    def _write_uninstaller(self):
        target = self.target
        menu = start_menu_dir()
        desktop = desktop_dir()
        bat_path = os.path.join(target, "Uninstall Dynamic Pro ERP.bat")
        lines = [
            "@echo off",
            "title Uninstall Dynamic Pro ERP",
            'taskkill /IM "DynamicPro.exe" /F >nul 2>&1',
            'del /q "%s\\Dynamic Pro ERP.lnk" 2>nul' % desktop,
            'del /q "%s\\Dynamic Pro ERP.lnk" 2>nul' % menu,
            'del /q "%s\\Uninstall Dynamic Pro ERP.lnk" 2>nul' % menu,
            'reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v DynamicProServer /f >nul 2>&1',
            'rmdir /s /q "%s" 2>nul' % menu,
            'cd /d "%TEMP%"',
            'rmdir /s /q "%s" 2>nul' % target.rstrip("\\"),
            'del "%~f0"',
        ]
        with open(bat_path, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("\n".join(lines))
        make_shortcut(os.path.join(menu, "Uninstall Dynamic Pro ERP.lnk"), bat_path)

    def _show_done(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._header(self)
        card = self._card(self)
        tk.Label(card, text="Installation Complete", bg=CARD, fg=GREEN, font=("Segoe UI", 16, "bold"), anchor="w").pack(fill="x", pady=(10, 14))
        tk.Label(card, text="Dynamic Pro ERP is ready. WebView2 Runtime is installed when needed and the application uses its local SQLite data directory.", bg=CARD, fg=MUTED, font=("Segoe UI", 10), anchor="w", wraplength=580).pack(fill="x", pady=(0, 12))
        tk.Label(card, text=self.target, bg="#f9fafb", fg=TEXT, font=("Segoe UI", 9), anchor="w").pack(fill="x", ipady=8)
        footer = tk.Frame(self, bg=BG, padx=24, pady=16)
        footer.pack(fill="x")
        tk.Button(footer, text="Launch Dynamic Pro ERP", font=("Segoe UI", 11, "bold"), bg=PRIMARY, fg="white", padx=20, pady=7, relief="flat", command=self._launch_installed).pack(side="left")
        tk.Button(footer, text="Close", font=("Segoe UI", 10), bg=BG, fg=TEXT, padx=18, pady=7, relief="flat", command=self.destroy).pack(side="left")

    def _launch_installed(self):
        subprocess.Popen([os.path.join(self.target, SERVER_EXE)], cwd=self.target)
        self.destroy()


def main():
    if os.environ.get("DYNAMICPRO_SETUP_INSTALL_SMOKE_TEST") == "1":
        try:
            run_install_smoke_test()
        except Exception as exc:
            print("DYNAMICPRO INSTALL SMOKE TEST: FAIL: %s" % exc, file=sys.stderr, flush=True)
            return 1
        return 0
    if os.environ.get("DYNAMICPRO_SETUP_SMOKE_TEST") == "1":
        try:
            run_smoke_test()
        except Exception as exc:
            print("DYNAMICPRO SETUP SMOKE TEST: FAIL: %s" % exc, file=sys.stderr, flush=True)
            return 1
        return 0
    InstallerApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
