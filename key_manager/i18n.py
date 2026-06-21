"""Internationalization (i18n) module for API Key Manager."""

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

_I18N_DIR = Path(__file__).parent / "i18n"
_DEFAULT_LANG = "en"
_fallback_chain: list[str] = [_DEFAULT_LANG]

_translations: dict[str, dict[str, str]] = {}
_lock = threading.Lock()
_context = threading.local()


def _load_lang(lang: str) -> dict[str, str]:
    """Load translations for a language from its JSON file, with caching."""
    with _lock:
        if lang in _translations:
            return _translations[lang]
    path = _I18N_DIR / f"{lang}.json"
    if not path.exists():
        with _lock:
            _translations[lang] = {}
        return {}
    with open(path, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)
    with _lock:
        _translations[lang] = data
    return data


def _get_current_lang() -> str:
    """Get the current language from thread-local context, or default."""
    return getattr(_context, "lang", _DEFAULT_LANG)


def set_lang(lang: str) -> None:
    """Set the current language for the calling thread."""
    _context.lang = lang


@contextmanager
def language_context(lang: str):
    """Context manager to temporarily set the active language."""
    prev = getattr(_context, "lang", None)
    _context.lang = lang
    try:
        yield
    finally:
        if prev is None:
            _context.lang = _DEFAULT_LANG
        else:
            _context.lang = prev


def get_lang_from_header(accept_language: Optional[str]) -> str:
    """Parse Accept-Language header and return the best matching language.

    Supports formats like:
    - "zh-CN,zh;q=0.9,en;q=0.8"
    - "en-US,en;q=0.9"
    - "zh"
    - "fr"
    """
    if not accept_language or not accept_language.strip():
        return _DEFAULT_LANG

    available = {p.stem for p in _I18N_DIR.glob("*.json")} if _I18N_DIR.exists() else set()

    candidates: list[tuple[str, float]] = []
    for part in accept_language.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(";")
        lang_tag = pieces[0].strip().lower()
        quality = 1.0
        if len(pieces) > 1:
            for param in pieces[1:]:
                param = param.strip()
                if param.startswith("q="):
                    try:
                        quality = float(param[2:])
                    except ValueError:
                        quality = 0.0
        if lang_tag:
            candidates.append((lang_tag, quality))

    candidates.sort(key=lambda x: x[1], reverse=True)

    for lang_tag, _ in candidates:
        if lang_tag in available:
            return lang_tag
        primary = lang_tag.split("-")[0]
        if primary in available:
            return primary

    return _DEFAULT_LANG


def t(code: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """Translate a message code to the current or specified language.

    Falls back to English if the code is not found in the requested language.
    Supports {key} placeholder substitution via kwargs.
    """
    target_lang = lang or _get_current_lang()

    # Try requested language first
    translations = _load_lang(target_lang)
    message = translations.get(code)

    # Walk fallback chain if missing
    if message is None and target_lang != _DEFAULT_LANG:
        for fb_lang in _fallback_chain:
            if fb_lang == target_lang:
                continue
            fb_translations = _load_lang(fb_lang)
            message = fb_translations.get(code)
            if message is not None:
                break

    # Ultimate fallback: return the raw code
    if message is None:
        message = code

    if kwargs:
        try:
            message = message.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass

    return message


def reload_translations() -> None:
    """Clear the translation cache, forcing reload on next access."""
    with _lock:
        _translations.clear()
