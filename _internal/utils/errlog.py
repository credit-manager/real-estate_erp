"""مساعد تسجيل الأخطاء الموحد.

الهدف: منع ابتلاع الأخطاء بصمت في كتل `except Exception` الواسعة —
كل استثناء يُسجَّل في سجل التطبيق (logging) مع السياق قبل المتابعة.

الاستخدام:
    from utils.errlog import log_exc

    try:
        ...
    except Exception:
        log_exc("license.login-notify")
"""
import logging
from typing import Optional

from utils.logging_setup import APP_LOGGER_NAME, configure_logging

logger: logging.Logger = logging.getLogger(APP_LOGGER_NAME)


def _ensure_handler() -> None:
    """يضمن ضبط المعالجات عبر الـ logging المركزي (بدون تكرار)."""
    configure_logging()


def log_exc(context: str, exc: Optional[Exception] = None) -> None:
    """يسجل الاستثناء الحالي مع وسم سياقي يحدد موضع الفشل."""
    _ensure_handler()
    if exc is None:
        logger.exception("ignored-error at %s", context, stacklevel=2)
    else:
        logger.error("error at %s: %s", context, exc, exc_info=True, stacklevel=2)
