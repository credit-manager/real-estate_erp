"""توليد أرقام مستندات آمنة ضد سباق التزامن.

المشكلة: توليد الرقم عبر MAX(id)+1 أو آخر رقم + 1 يسمح لطلبين متزامنين
بتوليد نفس الرقم، فيفشل أحدهما بـ IntegrityError (قيد unique).

الحل المركزي هنا:
  1) next_number(): توليد الرقم بنفس صيغة الوحدات القديمة.
  2) commit_with_retry(): يحفظ ويعيد التوليد عند تعارض الرقم (سباق).

الاستخدام:
    from utils.docnum import next_number, commit_with_retry

    order = SalesOrder(order_number=next_number(...), ...)
    db.session.add(order)
    commit_with_retry(order, "order_number", lambda: next_number(...))
"""
import logging
import random
import time
from typing import Any, Callable, Optional, Type

from database import db
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _seq_from_last(value: Any, fallback: int = 1) -> int:
    """يستخرج الرقم التسلسلي من نهاية نص مثل 'INV-2026-0042'."""
    try:
        return int(str(value).rsplit("-", 1)[-1]) + 1
    except (ValueError, IndexError, TypeError):
        return fallback


def seq_after_max(model: Any, fmt: str) -> str:
    """رقم تسلسلي مبني على أعلى id في الجدول: fmt يجب أن يقبل {n}."""
    last = model.query.order_by(model.id.desc()).first()
    n = (last.id + 1) if last else 1
    return fmt.format(n=n)


def seq_by_prefix(model: Any, col: Any, full_prefix: str, width: int = 4) -> str:
    """رقم تسلسلي سنوي: أعلى رقم حالات اللاحقة ثم +1 (مثل INV-2026-0001)."""
    last = (
        model.query.filter(col.like(full_prefix + "%"))
        .order_by(model.id.desc())
        .first()
    )
    seq = _seq_from_last(getattr(last, col.name)) if last else 1
    return f"{full_prefix}{seq:0{width}d}"


def commit_with_retry(
    record: Any,
    attr: str,
    generator: Callable[[], str],
    max_attempts: int = 5,
) -> bool:
    """يحفظ السجل؛ عند تعارض الرقم التسلسلي يعيد التوليد ويحاول مجدداً.

    تُستخدم مع أي سجل يحمل رقماً فريداً مولّداً تلقائياً. ترمي IntegrityError
    بعد استنفاد المحاولات (خطأ حقيقي وليس سباقاً).
    """
    for attempt in range(max_attempts):
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            if attempt == max_attempts - 1:
                raise
            setattr(record, attr, generator())
            # عشوائية صغيرة لتقليل تصادم المحاولات بين العمليات المتزامنة
            time.sleep(random.uniform(0.01, 0.05))
    return False
