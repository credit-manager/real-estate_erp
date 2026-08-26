import os
import tempfile
import glob
import subprocess
import winreg
import traceback
import installer

installer.messagebox.showerror = lambda title, msg: print("SHOWERROR:", title, "|", msg)

_desktop = os.path.join(tempfile.mkdtemp(), "Desktop")
_startmenu = os.path.join(tempfile.mkdtemp(), "StartMenu")
os.makedirs(_desktop)
os.makedirs(_startmenu)
installer.desktop_dir = lambda: _desktop
installer.start_menu_dir = lambda: _startmenu

app = installer.InstallerApp()
tmp = tempfile.mkdtemp()
app.target = os.path.join(tmp, "DynamicProTest")
app.source = installer.default_source_dir()
app.exes = installer.find_exes(app.source)
app.opt_desktop = installer.tk.BooleanVar(value=True)
app.opt_startmenu = installer.tk.BooleanVar(value=True)
app.opt_autostart = installer.tk.BooleanVar(value=True)
app.progress = installer.ttk.Progressbar(app, maximum=100, mode="determinate")

app._do_install()
app.update()

target = app.target
print("installed files:", sorted(os.listdir(target)))
assert installer.SERVER_EXE in os.listdir(target)
assert installer.CLIENT_EXE in os.listdir(target)

desktop = installer.desktop_dir()
sm = installer.start_menu_dir()
print("desktop lnk:", [os.path.basename(p) for p in glob.glob(os.path.join(desktop, "*.lnk"))])
print("startmenu lnk:", [os.path.basename(p) for p in glob.glob(os.path.join(sm, "*.lnk"))])
assert glob.glob(os.path.join(desktop, "*.lnk"))
assert glob.glob(os.path.join(sm, "*.lnk"))

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.RUN_KEY) as k:
    val, _ = winreg.QueryValueEx(k, installer.RUN_VALUE)
print("run value:", val)
assert "--background" in val and "DynamicProTest" in val
installer.disable_autostart()

assert os.path.exists(os.path.join(target, "Uninstall Dynamic Pro ERP.bat"))
print("uninstaller: OK")

app.destroy()
print("ALL TESTS PASSED")
