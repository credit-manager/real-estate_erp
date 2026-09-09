# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the self-contained Dynamic Pro desktop app."""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "app",
    "live_pdf_builder",
    "email",
    "email.message",
    "email.policy",
    "email.parser",
    "email.feedparser",
    "email.header",
    "email.utils",
    "email.mime",
    "http.server",
    "werkzeug.serving",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]

# The application uses many dynamic local imports for blueprints and models.
for package in ("models", "routes", "security", "licensing", "utils"):
    hiddenimports.extend(collect_submodules(package))


a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("app.ico", "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_cov"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DynamicPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["app.ico"],
)
