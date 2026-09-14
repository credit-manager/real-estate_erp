"""Translations loader: Arabic (ar) / English (en).

Flat keys with dot notation (e.g. "nav.projects").
Dictionaries live in i18n_ar.py / i18n_en.py (auto-split).
"""
from typing import Callable, Dict, Optional

DEFAULT_LANG: str = "ar"
LANG_CODES: list = ["ar", "en"]

from i18n_ar import TRANSLATIONS_AR  # noqa: E402
from i18n_en import TRANSLATIONS_EN  # noqa: E402

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ar": TRANSLATIONS_AR,
    "en": TRANSLATIONS_EN,
}


def get_lang() -> str:
    """Get the current language from the request cookie."""
    from flask import request
    lang = request.cookies.get("lang", DEFAULT_LANG)
    if lang not in LANG_CODES:
        lang = DEFAULT_LANG
    return lang


def make_t(lang: Optional[str] = None) -> Callable[[str], str]:
    """Create a translation function for the given language."""
    lang = lang or get_lang()

    def t(key: str) -> str:
        return TRANSLATIONS[lang].get(key, key)

    return t
