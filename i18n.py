"""Translations loader: Arabic (ar) / English (en).

Flat keys with dot notation (e.g. "nav.projects").
Dictionaries live in i18n_ar.py / i18n_en.py (auto-split).
"""

DEFAULT_LANG = "ar"
LANG_CODES = ["ar", "en"]

from i18n_ar import TRANSLATIONS_AR  # noqa: E402
from i18n_en import TRANSLATIONS_EN  # noqa: E402

TRANSLATIONS = {
    "ar": TRANSLATIONS_AR,
    "en": TRANSLATIONS_EN,
}


def get_lang():
    from flask import request
    lang = request.cookies.get("lang", DEFAULT_LANG)
    if lang not in LANG_CODES:
        lang = DEFAULT_LANG
    return lang


def make_t(lang=None):
    lang = lang or get_lang()

    def t(key):
        return TRANSLATIONS[lang].get(key, key)

    return t
