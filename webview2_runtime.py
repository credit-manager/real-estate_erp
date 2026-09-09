"""Offline Microsoft Edge WebView2 Evergreen Runtime deployment helpers."""

import os
import subprocess
import sys
import winreg

WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"


def _read_pv(root, path):
    try:
        with winreg.OpenKey(root, path) as key:
            value, value_type = winreg.QueryValueEx(key, "pv")
            if value_type != winreg.REG_SZ or not value:
                return None
            return str(value).strip()
    except OSError:
        return None


def get_installed_version():
    """Return the registered WebView2 Runtime version, or None when absent."""
    candidates = [
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%s" % WEBVIEW2_CLIENT_GUID,
        ),
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\EdgeUpdate\Clients\%s" % WEBVIEW2_CLIENT_GUID,
        ),
    ]
    if sys.maxsize <= 2**32:
        candidates = [
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\EdgeUpdate\Clients\%s" % WEBVIEW2_CLIENT_GUID,
            ),
            candidates[1],
        ]

    versions = []
    for root, path in candidates:
        value = _read_pv(root, path)
        if value:
            try:
                if tuple(int(part) for part in value.split(".")[:4]) > (0, 0, 0, 0):
                    versions.append(value)
            except ValueError:
                continue
    return max(versions, key=lambda v: tuple(int(p) for p in v.split(".")[:4])) if versions else None


def is_installed():
    return get_installed_version() is not None


def installer_path(resource_path):
    path = os.path.join(resource_path, WEBVIEW2_INSTALLER)
    return path if os.path.isfile(path) else None


def install_if_missing(resource_path):
    """Install the bundled Evergreen Standalone Runtime when it is absent."""
    if is_installed():
        return False

    installer = installer_path(resource_path)
    if not installer:
        raise RuntimeError(
            "WebView2 Runtime is missing and the offline installer was not bundled."
        )

    result = subprocess.run(
        [installer, "/silent", "/install"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode not in (0, 3010):
        raise RuntimeError(
            "WebView2 Runtime installation failed with exit code %s." % result.returncode
        )

    if not is_installed():
        raise RuntimeError("WebView2 Runtime installer completed but the runtime was not registered.")
    return True
