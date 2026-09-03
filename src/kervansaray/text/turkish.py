"""Turkce metin normalizasyonu.

`turkish_lower()` CILEKAI `core/faq_manager.py`'den birebir tasindi
(PROJECT_BRIEF S13 - "Turkish text normalisation helpers"). Python'un
`str.lower()`'i Turkce I/i ciftini yanlis cevirir.
"""
from __future__ import annotations

import re

_UPPER_TO_LOWER = {
    "İ": "i",
    "I": "ı",
    "Ğ": "ğ",
    "Ü": "ü",
    "Ş": "ş",
    "Ö": "ö",
    "Ç": "ç",
}

# Aksan/ozel harf -> ASCII (deterministik arama/eslestirme icin)
_TO_ASCII = str.maketrans({
    "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
})


def turkish_lower(text: str) -> str:
    """Turkce kurallarina gore kucuk harfe cevirir."""
    for upper, lower in _UPPER_TO_LOWER.items():
        text = text.replace(upper, lower)
    return text.lower()


def normalize_whitespace(text: str) -> str:
    """Bastaki/sondaki bosluklari kirpar, ic bosluklari teke indirir."""
    return re.sub(r"\s+", " ", text).strip()


def to_ascii(text: str) -> str:
    """Turkce harfleri ASCII karsiliklariyla degistirir (kucuk harf sonucu)."""
    return turkish_lower(text).translate(_TO_ASCII)


def normalize_query(text: str) -> str:
    """Serbest metin sorgu icin standart normalizasyon: lower + tek bosluk."""
    return normalize_whitespace(turkish_lower(text))
