"""Dynamic Pro ERP - Setup.

Self-contained installer for the two packaged apps (DynamicPro.exe and
DynamicPro-Client.exe). It must be placed next to those files (in the dist
folder). Installs to %LOCALAPPDATA%\\Programs\\Dynamic Pro ERP, creates
Desktop + Start Menu shortcuts and optionally enables Windows auto-start
for the server (background mode).
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import winreg
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Dynamic Pro ERP"
APP_VERSION = "1.0.0"
SERVER_EXE = "DynamicPro.exe"
CLIENT_EXE = "DynamicPro-Client.exe"
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
    return getattr(sys, "frozen", False)


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def default_source_dir():
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")


def find_exes(folder):
    found = {}
    for exe in (SERVER_EXE, CLIENT_EXE):
        path = os.path.join(folder, exe)
        if os.path.isfile(path):
            found[exe] = path
    return found


def desktop_dir():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
            if value:
                value = os.path.expandvars(value)
                if os.path.isdir(value):
                    return value
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def start_menu_dir():
    base = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
    )
    return os.path.join(base, APP_NAME)


def make_shortcut(lnk_path, target, icon=None, args=""):
    if icon is None:
        icon = target
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath = '%s';"
        "$s.Arguments = '%s';"
        "$s.IconLocation = '%s,0';"
        "$s.Save()"
        % (lnk_path.replace("'", "''"), target.replace("'", "''"),
           args.replace("'", "''"), icon.replace("'", "''"))
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def enable_autostart(exe_path):
    cmd = '"%s" --background' % exe_path
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, cmd)


def disable_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except OSError:
        pass


def is_running(exe_name):
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % exe_name],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout
    return exe_name.lower() in out.lower()


def taskkill(exe_name):
    subprocess.run(
        ["taskkill", "/IM", exe_name, "/F"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dynamic Pro ERP - Setup")
        self.geometry("680x620")
        self.minsize(660, 600)
        self.configure(bg=BG)
        self.resizable(False, False)
        try:
            self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass

        self.target = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "Programs",
            INSTALL_SUBDIR,
        )
        self.source = default_source_dir()
        self.exes = find_exes(self.source)
        self.src_var = tk.StringVar(value=self.source)
        self.dst_var = tk.StringVar(value=self.target)

        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except Exception:
            pass
        self._style.configure(
            "TProgressbar", troughcolor="#e5e7eb", background=PRIMARY,
            borderwidth=0, thickness=10,
        )

        self._build_welcome()

    # ---------- widgets ----------
    def _header(self, parent):
        header = tk.Frame(parent, bg=PRIMARY, height=96)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = tk.Frame(header, bg=PRIMARY)
        inner.pack(fill="both", expand=True, padx=28, pady=18)

        badge = tk.Label(
            inner, text="DP", bg="#3b82f6", fg="white",
            font=("Segoe UI", 20, "bold"), width=3, height=1,
        )
        badge.pack(side="left", padx=(0, 16), pady=0)
        badge.pack_propagate(False)
        badge.config(width=4, height=2)

        text = tk.Frame(inner, bg=PRIMARY)
        text.pack(side="left", fill="both", expand=True)
        tk.Label(
            text, text=APP_NAME, bg=PRIMARY, fg="white",
            font=("Segoe UI", 18, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            text, text="Setup - Server & Client applications",
            bg=PRIMARY, fg="#bfdbfe", font=("Segoe UI", 10), anchor="w",
        ).pack(fill="x")

        ver = tk.Label(
            header, text="v" + APP_VERSION, bg="#1e40af", fg="#93c5fd",
            font=("Segoe UI", 9, "bold"), padx=10, pady=4,
        )
        ver.place(relx=1.0, rely=0.0, x=-14, y=10, anchor="ne")

    def _card(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=24, pady=20)
        card.pack(fill="both", expand=True, padx=24, pady=(18, 10))
        return card

    def _field_label(self, parent, text):
        tk.Label(
            parent, text=text, bg=CARD, fg=TEXT,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 4))

    def _path_row(self, parent, variable, browse_cmd):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, 14))
        entry = tk.Entry(
            row, textvariable=variable, font=("Segoe UI", 10),
            bg="#f9fafb", fg=TEXT, relief="solid", bd=1,
            highlightthickness=1, highlightcolor="#d1d5db",
            highlightbackground="#d1d5db",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(
            row, text="Browse...", font=("Segoe UI", 10), bg="#f3f4f6",
            fg=TEXT, relief="solid", bd=1, padx=14, activebackground="#e5e7eb",
            command=browse_cmd,
        ).pack(side="left", padx=(8, 0), ipady=3)

    def _primary_btn(self, parent, text, command, state="normal"):
        btn = tk.Button(
            parent, text=text, font=("Segoe UI", 11, "bold"), bg=PRIMARY,
            fg="white", padx=26, pady=6, relief="flat",
            activebackground=PRIMARY_DARK, activeforeground="white",
            disabledforeground="#93c5fd", cursor="hand2", command=command,
        )
        btn.config(state=state)
        btn.pack(side="left")
        return btn

    def _ghost_btn(self, parent, text, command):
        tk.Button(
            parent, text=text, font=("Segoe UI", 10), bg=BG, fg=TEXT,
            padx=18, pady=6, relief="flat", activebackground="#e5e7eb",
            cursor="hand2", command=command,
        ).pack(side="left", padx=(0, 10))

    # ---------- screen: welcome ----------
    def _build_welcome(self):
        for w in self.winfo_children():
            w.destroy()

        self._header(self)
        card = self._card(self)

        self._field_label(card, "Application files location")
        self._path_row(card, self.src_var, self._browse_source)

        self._field_label(card, "Installation folder")
        self._path_row(card, self.dst_var, self._browse_dest)

        opts = tk.Frame(card, bg=CARD)
        opts.pack(fill="x", pady=(0, 14))

        self.opt_desktop = tk.BooleanVar(value=True)
        self.opt_startmenu = tk.BooleanVar(value=True)
        self.opt_autostart = tk.BooleanVar(value=True)

        for var, text in (
            (self.opt_desktop, "Create Desktop shortcuts"),
            (self.opt_startmenu, "Add to Start Menu"),
            (self.opt_autostart, "Start the server automatically with Windows (background)"),
        ):
            tk.Checkbutton(
                opts, text=text, variable=var, bg=CARD, fg=TEXT,
                font=("Segoe UI", 10), activebackground=CARD,
                activeforeground=TEXT, anchor="w", selectcolor="#e0e7ff",
                highlightthickness=0, bd=0, cursor="hand2",
            ).pack(fill="x", pady=2)

        tk.Frame(card, bg="#e5e7eb", height=1).pack(fill="x", pady=(0, 14))

        info = tk.Frame(card, bg="#eff6ff", padx=14, pady=10)
        info.pack(fill="x")
        tk.Label(
            info, text="This will install:", bg="#eff6ff", fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            info, text="  - Dynamic Pro ERP - Server  (%s)" % SERVER_EXE,
            bg="#eff6ff", fg=TEXT, font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x")
        tk.Label(
            info, text="  - Dynamic Pro ERP - Client  (%s)" % CLIENT_EXE,
            bg="#eff6ff", fg=TEXT, font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x")

        self.status = tk.Label(
            card, text="", bg=CARD, fg=GREEN, font=("Segoe UI", 10),
            justify="left", anchor="w", wraplength=580,
        )
        self.status.pack(fill="x", pady=(12, 8))

        self.progress = ttk.Progressbar(
            card, style="TProgressbar", maximum=100, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.pack_forget()

        footer = tk.Frame(self, bg=BG, padx=24, pady=16)
        footer.pack(fill="x")
        self.install_btn = self._primary_btn(footer, "Install", self._install)
        self._ghost_btn(footer, "Cancel", self.destroy)

        self._refresh_status()

    def _browse_source(self):
        folder = filedialog.askdirectory(initialdir=self.source, title="Select application files folder")
        if folder:
            self.source = folder
            self.src_var.set(folder)
            self._refresh_status()

    def _browse_dest(self):
        folder = filedialog.askdirectory(initialdir=self.dst_var.get(), title="Select installation folder")
        if folder:
            self.dst_var.set(folder)

    def _refresh_status(self):
        self.exes = find_exes(self.source)
        if len(self.exes) == 2:
            self.status.config(
                text="Ready to install - server and client applications found.",
                fg=GREEN)
            self.install_btn.config(state="normal")
        else:
            missing = [e for e in (SERVER_EXE, CLIENT_EXE) if e not in self.exes]
            self.status.config(
                text="Missing files: %s.\nThe setup must be placed next to both "
                     "files in the dist folder." % ", ".join(missing),
                fg=AMBER)
            self.install_btn.config(state="disabled")

    # ---------- install ----------
    def _install(self):
        self.source = self.src_var.get()
        self.target = self.dst_var.get().strip()
        self.exes = find_exes(self.source)
        if len(self.exes) != 2:
            self._refresh_status()
            return

        running = [e for e in self.exes if is_running(e)]
        if running:
            if not messagebox.askyesno(
                    "Applications in use",
                    "The following applications are running and will be closed:\n\n" +
                    "\n".join(running) + "\n\nContinue?"):
                return
            for e in running:
                taskkill(e)

        self.install_btn.config(state="disabled", text="Installing...")
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.config(value=0)
        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self):
        def set_status(msg, pct=None):
            self.after(0, lambda: self.status.config(text=msg, fg=PRIMARY_DARK))
            if pct is not None:
                self.after(0, lambda: self.progress.config(value=pct))

        try:
            set_status("Preparing folders...", 10)
            os.makedirs(self.target, exist_ok=True)

            for idx, exe in enumerate((SERVER_EXE, CLIENT_EXE)):
                set_status("Copying %s ..." % exe, 15 + idx * 25)
                src = os.path.join(self.source, exe)
                dst = os.path.join(self.target, exe)
                for attempt in range(3):
                    try:
                        shutil.copy2(src, dst)
                        break
                    except PermissionError:
                        taskkill(exe)
                        time.sleep(1)
                else:
                    raise RuntimeError("Could not copy %s (file is in use)" % exe)

            shortcuts = []

            if self.opt_desktop.get():
                set_status("Creating Desktop shortcuts...", 65)
                d = desktop_dir()
                shortcuts.append((os.path.join(d, "Dynamic Pro (Server).lnk"),
                                  os.path.join(self.target, SERVER_EXE), None, ""))
                shortcuts.append((os.path.join(d, "Dynamic Pro (Client).lnk"),
                                  os.path.join(self.target, CLIENT_EXE), None, ""))

            if self.opt_startmenu.get():
                set_status("Creating Start Menu shortcuts...", 70)
                sm = start_menu_dir()
                os.makedirs(sm, exist_ok=True)
                shortcuts.append((os.path.join(sm, "Dynamic Pro (Server).lnk"),
                                  os.path.join(self.target, SERVER_EXE), None, ""))
                shortcuts.append((os.path.join(sm, "Dynamic Pro (Client).lnk"),
                                  os.path.join(self.target, CLIENT_EXE), None, ""))

            for lnk, tgt, icon, args in shortcuts:
                make_shortcut(lnk, tgt, icon, args)

            if self.opt_autostart.get():
                set_status("Enabling auto-start...", 85)
                enable_autostart(os.path.join(self.target, SERVER_EXE))

            set_status("Creating uninstaller...", 92)
            self._write_uninstaller()

            self.after(0, lambda: self.progress.config(value=100))
            self.after(0, self._show_done)
        except Exception as exc:
            err = exc
            self.after(0, lambda: messagebox.showerror(
                "Error", "Installation failed:\n%s" % err))
            self.after(0, lambda: (self.install_btn.config(
                state="normal", text="Install"), self._refresh_status(),
                self.progress.config(value=0)))

    def _write_uninstaller(self):
        desktop = desktop_dir()
        sm = start_menu_dir()
        target = self.target
        bat_path = os.path.join(target, "Uninstall Dynamic Pro ERP.bat")
        lines = [
            "@echo off",
            "title Uninstall Dynamic Pro ERP",
            "echo Removing Dynamic Pro ERP...",
            'del /q "%s\\Dynamic Pro (Server).lnk" 2>nul' % desktop,
            'del /q "%s\\Dynamic Pro (Client).lnk" 2>nul' % desktop,
            'del /q "%s\\Dynamic Pro (Server).lnk" 2>nul' % sm,
            'del /q "%s\\Dynamic Pro (Client).lnk" 2>nul' % sm,
            'del /q "%s\\Uninstall Dynamic Pro ERP.lnk" 2>nul' % sm,
            'reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v DynamicProServer /f 2>nul',
            'cd /d "C:\\"',
            'rmdir /s /q "%s" 2>nul' % sm,
            'rmdir /s /q "%s" 2>nul' % target.rstrip("\\"),
            'del "%~f0"',
        ]
        with open(bat_path, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("\n".join(lines))

        icon = bat_path
        if os.path.isfile(resource_path("app.ico")):
            icon = os.path.join(
                os.path.dirname(sys.executable if is_frozen() else os.path.abspath(__file__)),
                "app.ico")
        make_shortcut(os.path.join(sm, "Uninstall Dynamic Pro ERP.lnk"),
                      bat_path, icon, "")

    # ---------- screen: done ----------
    def _show_done(self):
        for w in self.winfo_children():
            w.destroy()

        self._header(self)
        card = self._card(self)

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", pady=(10, 8))

        check = tk.Label(
            top, text="\u2713", bg="#10b981", fg="white",
            font=("Segoe UI", 20, "bold"), width=3, height=1,
        )
        check.pack(side="left", padx=(0, 16))
        check.pack_propagate(False)
        check.config(width=3, height=1)

        texts = tk.Frame(top, bg=CARD)
        texts.pack(side="left", fill="both", expand=True)
        tk.Label(
            texts, text="Installation Complete", bg=CARD, fg=GREEN,
            font=("Segoe UI", 16, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            texts, text="Dynamic Pro ERP has been installed successfully.",
            bg=CARD, fg=MUTED, font=("Segoe UI", 10), anchor="w",
        ).pack(fill="x")

        tk.Frame(card, bg="#e5e7eb", height=1).pack(fill="x", pady=14)

        tk.Label(
            card, text="Installed to:", bg=CARD, fg=TEXT,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            card, text=self.target, bg="#f9fafb", fg=TEXT,
            font=("Consolas", 9), anchor="w", padx=12, pady=8,
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground="#e5e7eb",
        ).pack(fill="x", pady=(2, 0))

        if self.opt_autostart.get():
            tk.Label(
                card, text="Auto-start with Windows is enabled.",
                bg=CARD, fg=MUTED, font=("Segoe UI", 10), anchor="w",
            ).pack(fill="x", pady=(12, 0))

        footer = tk.Frame(self, bg=BG, padx=24, pady=16)
        footer.pack(fill="x")
        self._primary_btn(footer, "Launch Dynamic Pro now", self._launch)
        self._ghost_btn(footer, "Finish", self.destroy)

    def _launch(self):
        subprocess.Popen([os.path.join(self.target, SERVER_EXE)])


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
