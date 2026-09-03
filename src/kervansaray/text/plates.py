"""Turk plakasi kanoniklestirme ve dogrulama.

CILEKAI'da yoktu - bu proje icin yazildi. Gerekce PROJECT_BRIEF:
  - S3.5: "34 abc 123", "34-ABC-123", "34abc123" -> kanonik forma
    cevrilmeli (lookup ONCESI, deterministik olarak).
  - S4.1: gecerli plaka dilbilgisi
        il kodu : 01-81
        sonra   : 1 harf + 4 rakam | 2 harf + 3 rakam | 3 harf + 2 rakam

Not: Brief S4.1'deki liste sadelestirilmis - kendi S6 ornek plakasi
"34ABC123" (3 harf + 3 rakam) bu listede yok. Gercek Turk plakalarinda
kullanilan kombinasyonlar asagidaki _VALID_SHAPES kumesinde tutulur;
liste tek yerden guncellenebilir.

Kanonik form: bosluksuz, buyuk harf, Turkce harf yok -> "34ABC123".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Turkce harfler plakada kullanilmaz; olasi OCR/giris hatalarini duzelt.
_TR_FIX = str.maketrans({"İ": "I", "I": "I", "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C"})

_CANON_RE = re.compile(r"^(\d{2})([A-Z]{1,3})(\d{2,4})$")

# (harf adedi, rakam adedi) gecerli kombinasyonlar.
# Brief S4.1 taban alindi + gercekte yaygin olan (2,4) ve (3,3) eklendi.
_VALID_SHAPES = {
    (1, 4),
    (2, 3),
    (2, 4),
    (3, 2),
    (3, 3),
}


@dataclass(frozen=True)
class PlateParse:
    canonical: str
    province: int
    letters: str
    digits: str
    valid: bool
    reason: str = ""


def canonicalize(raw: str) -> str:
    """Serbest girisi bosluksuz buyuk-harf forma indirger. Dogrulama yapmaz."""
    s = raw.strip().upper().translate(_TR_FIX)
    s = re.sub(r"[\s\-_.]", "", s)
    return s


def parse(raw: str) -> PlateParse:
    """Kanoniklestir + S4.1 dilbilgisine gore dogrula."""
    canon = canonicalize(raw)
    m = _CANON_RE.match(canon)
    if not m:
        return PlateParse(canon, 0, "", "", False, "format taninmadi")

    province = int(m.group(1))
    letters, digits = m.group(2), m.group(3)

    if not (1 <= province <= 81):
        return PlateParse(canon, province, letters, digits, False, "il kodu 01-81 disinda")

    if (len(letters), len(digits)) not in _VALID_SHAPES:
        return PlateParse(
            canon, province, letters, digits, False,
            f"gecersiz harf/rakam yapisi ({len(letters)}+{len(digits)})",
        )

    return PlateParse(canon, province, letters, digits, True)


def is_valid(raw: str) -> bool:
    return parse(raw).valid
