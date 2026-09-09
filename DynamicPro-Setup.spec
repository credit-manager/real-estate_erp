# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the single-file Dynamic Pro ERP installer."""

import os

server_exe = os.path.join("dist", "DynamicPro.exe")
if not os.path.isfile(server_exe):
    raise SystemExit(
        "DynamicPro-Setup.spec requires dist/DynamicPro.exe. "
        "Build DynamicPro.spec first."
    )

a = Analysis(
    ["installer.py"],
    pathex=["."],
    binaries=[],
    datas=[
        (server_exe, "."),
        ("app.ico", "."),
    ],
    hiddenimports=[],
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
