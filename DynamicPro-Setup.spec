# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the self-contained Dynamic Pro ERP installer."""

import os

server_exe = os.path.join("dist", "DynamicPro.exe")
webview2_installer = os.path.join(
    "assets",
    "webview2",
    "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
)

if not os.path.isfile(server_exe):
    raise SystemExit(
        "DynamicPro-Setup.spec requires dist/DynamicPro.exe. "
        "Build DynamicPro.spec first."
    )

if not os.path.isfile(webview2_installer):
    raise SystemExit(
        "DynamicPro-Setup.spec requires the Microsoft WebView2 Evergreen "
        "Standalone x64 installer at " + webview2_installer
    )

a = Analysis(
    ["installer.py"],
    pathex=["."],
    binaries=[],
    datas=[
        (server_exe, "."),
        (webview2_installer, "."),
        ("app.ico", "."),
    ],
    hiddenimports=["webview2_runtime"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="DynamicPro-Setup",
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
