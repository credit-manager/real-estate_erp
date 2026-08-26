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
import sys

logger = logging.getLogger("dynamicpro")


def _ensure_handler():
    """يتأكد من وجود معالج واحد على الأقل (stderr + ملف logs/app.log عند الإمكان)."""
    if logger.handlers:
        return
    logger.setLevel(logging.WARNING)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass  # الملف اختياري — stderr متاح دائماً


def log_exc(context, exc=None):
    """يسجل الاستثناء الحالي مع وسم سياقي يحدد موضع الفشل."""
    _ensure_handler()
    if exc is None:
        logger.exception("ignored-error at %s", context, stacklevel=2)
    else:
        logger.error("error at %s: %s", context, exc, exc_info=True, stacklevel=2)
