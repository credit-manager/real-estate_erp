# -*- coding: utf-8 -*-
"""إعداد تسجيل مركزي (Logging Foundation).

يوفّر `configure_logging()` لضبط مستوى السجل وإضافة معالجات:
- وحدة تحكم (stderr) دائمة.
- ملف دوّار (RotatingFileHandler) بحجم أقصى معيّن في `logs/app.log`.

يُستدعى مرة واحدة من `create_app` في app.py. أي وحدة تستخدم
`logging.getLogger(...)` ستسجّل عبر هذه المعالجات دون الحاجة لضبطها بنفسها.

الاستخدام:
    from utils.logging_setup import configure_logging
    configure_logging()
"""
import logging
import os
from logging.handlers import RotatingFileHandler

APP_LOGGER_NAME = "dynamicpro"
SECURITY_LOGGER_NAME = "security"
DEFAULT_LEVEL = logging.INFO
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB لكل ملف
_BACKUP_COUNT = 5               # يحتفظ بآخر 5 ملفات دوّارة
_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _log_dir():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _make_formatter():
    return logging.Formatter(_FMT)


def configure_logging(level=None):
    """يضبط تسجيل التطبيق بمعالج كونسول + ملف دوّار (تجميعي idempotent)."""
    if level is None:
        level = os.environ.get("LOG_LEVEL", "").upper() or DEFAULT_LEVEL
        if not isinstance(level, int):
            try:
                level = getattr(logging, level, DEFAULT_LEVEL)
            except Exception:
                level = DEFAULT_LEVEL

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(level)

    # منع المعالجات المكررة عند إعادة التشغيل مع auto-reload
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        try:
            fh = RotatingFileHandler(
                os.path.join(_log_dir(), "app.log"),
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            fh.setFormatter(_make_formatter())
            fh.setLevel(level)
            logger.addHandler(fh)
        except Exception:
            pass  # الملف اختياري — console يتكفل بالحال

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(_make_formatter())
        sh.setLevel(level)
        logger.addHandler(sh)

    # جذر التطبيق (Flask logger) يتصل بنفس النواة
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.NullHandler())

    logger.debug("Logging configured (level=%s)", logging.getLevelName(level))

    # Phase 1 — attach the same file+console handlers to the security package
    # logger so RBAC / 2FA / JWT / audit logs appear in app.log.
    sec_logger = logging.getLogger(SECURITY_LOGGER_NAME)
    sec_logger.setLevel(level)
    for h in logger.handlers:
        if not any(isinstance(x, type(h)) and x.stream == h.stream for x in sec_logger.handlers):
            sec_logger.addHandler(h)

    # Also configure the licensing logger so master login/session logs appear.
    lic_logger = logging.getLogger("licensing")
    lic_logger.setLevel(level)
    for h in logger.handlers:
        if not any(isinstance(x, type(h)) and x.stream == h.stream for x in lic_logger.handlers):
            lic_logger.addHandler(h)

    return logger
