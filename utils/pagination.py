"""مساعدات الترقيم (Pagination) لقوائم واجهات API.

- التمرير الافتراضي يعيد مصفوفة محدودة بسقف أمان (متوافق مع الواجهات القديمة)
  بدلاً من سحب كل صفوف الجدول في استجابة واحدة.
- عند تمرير paged=1 يُعاد مغلف {items, total, page, per_page, pages} لصفحات
  الواجهة المطورة التي تعرض أزرار تنقل.
- page و per_page من query string، مع سقف أقصى لـ per_page.
"""
from datetime import datetime

from flask import request

DEFAULT_PER_PAGE = 100
MAX_PER_PAGE = 500
DEFAULT_CAP = 1000


def _int_arg(name, default):
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def paginate(query, serializer=None):
    """يطبق الترقيم على الاستعلام ويعيد (items, total, page, per_page, pages).

    items قائمة dicts جاهزة للترقيم. serializer اختياري لتحويل الصف (افتراضياً .to_dict).
    """
    ser = serializer or (lambda r: r.to_dict())
    page = max(_int_arg("page", 1), 1)
    per_page = min(max(_int_arg("per_page", DEFAULT_PER_PAGE), 1), MAX_PER_PAGE)
    total = query.count()
    pages = (total + per_page - 1) // per_page if per_page else 1
    if page > pages and pages > 0:
        page = pages
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    items = [ser(r) for r in rows]
    return items, total, page, per_page, pages


def response(items, total, page, per_page, pages):
    """مغلف الاستجابة للصفحات المطورة."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def is_paged():
    return request.args.get("paged") in ("1", "true", "yes")


def paged_or_cap(query, serializer=None):
    """واجهة موحدة: يرجع (items, envelope_or_None).

    - إذا طلب المتصل paged=1: يعيد مغلف الترقيم كامل.
    - خلاف ذلك: يعيد مصفوفة محدودة بسقف الأمان (بدون count كامل).
    """
    ser = serializer or (lambda r: r.to_dict())
    if is_paged():
        items, total, page, per_page, pages = paginate(query, serializer)
        return items, response(items, total, page, per_page, pages)
    items = query.limit(DEFAULT_CAP).all()
    return [ser(r) for r in items], None


def parse_date(value):
    """يحلل تاريخ YYYY-MM-DD ويعيد date أو None."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
