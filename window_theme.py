"""Light (off-white) native title bar for the pywebview window on Windows.

Uses the Desktop Window Manager (DWM) API:
- Windows 10: light caption bar with dark text.
- Windows 11: additionally applies the off-white caption / border color.
"""
import ctypes
import logging

logger = logging.getLogger(__name__)

# DWMWINDOWATTRIBUTE ids (dwmapi.h)
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

OFF_WHITE = 0x00FBF8F6  # #F6F8FB (page background) as COLORREF (0x00BBGGRR)
DARK_TEXT = 0x003B291E  # #1E293B as COLORREF (0x00BBGGRR)
BORDER = 0x00F3EDE8  # #E8EDF3 as COLORREF (0x00BBGGRR)

_dwm = ctypes.WinDLL("dwmapi.dll")


def _set_attr(hwnd, attr, value):
    val = ctypes.c_uint(value)
    # DwmSetWindowAttribute(HWND, DWMWINDOWATTRIBUTE, LPCVOID, DWORD)
    return (
        _dwm.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), attr, ctypes.byref(val), ctypes.sizeof(val)
        )
        == 0
    )


def apply_light_titlebar(window):
    """Lighten the native title bar once the window is shown.

    Call with the Window object before ``webview.start()``.
    """

    def _on_shown(window):
        try:
            native = getattr(window, "native", None)
            if native is None:
                return
            hwnd = native.Handle.ToInt32()
            # Light caption bar with dark text (supported on Windows 10/11)
            _set_attr(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 0)
            # Off-white caption / text / border (Windows 11 only; safely
            # ignored on Windows 10 where the light caption remains).
            _set_attr(hwnd, DWMWA_CAPTION_COLOR, OFF_WHITE)
            _set_attr(hwnd, DWMWA_TEXT_COLOR, DARK_TEXT)
            _set_attr(hwnd, DWMWA_BORDER_COLOR, BORDER)
        except Exception:
            logger.exception("Failed to apply light title bar")

    try:
        window.events.shown += _on_shown
    except Exception:
        logger.exception("Failed to hook window shown event")
