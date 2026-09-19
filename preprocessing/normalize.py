"""Canonical text normalization used by both imports and incoming queries.

The functions in this module are intentionally deterministic and contain no
database-specific behaviour.  The same functions should be used while loading
the registry and while handling a search request.
"""

from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


def _require_text(value: str, field_name: str = "value") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _punctuation_to_spaces(value: str) -> str:
    """Replace punctuation/symbol runs with spaces without dropping word gaps."""

    return "".join(
        " " if unicodedata.category(character)[0] in {"P", "S"} else character
        for character in value
    )


def normalize_name(value: str) -> str:
    """Return the accent-preserving normalized representation of a name.

    Steps: Unicode compatibility normalization, case-folding, punctuation
    normalization, trimming, and whitespace collapsing.
    """

    text = _require_text(value)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _punctuation_to_spaces(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def remove_diacritics(value: str) -> str:
    """Remove combining marks and map Vietnamese ``đ``/``Đ`` to ``d``/``D``."""

    text = _require_text(value)
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return unicodedata.normalize("NFC", without_marks)


def to_search_key(value: str) -> str:
    """Return the lowercase, punctuation-free, accent-insensitive search key."""

    return remove_diacritics(normalize_name(value))
