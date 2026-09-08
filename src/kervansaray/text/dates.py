"""Deterministik Turkce tarih ve goreceli zaman cozumleyici (PROJECT_BRIEF S3.5).

Modele tarih aritmetigi yaptirilmaz; "dun gece", "gecen hafta", "15 Nisan" gibi
kalip ve ifadeler mutlak [start, end) datetime araligina cevrilir.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .turkish import to_ascii

TR = timezone(timedelta(hours=3))  # UTC+3 (Turkiye, DST yok)

_MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
}


def resolve_time_range(
    text: str, *, as_of: datetime | None = None
) -> tuple[datetime, datetime] | None:
    """Verilen serbest metindeki Turkce tarih kaliplarini cozer.

    Bulamazsa None doner. Donen datetime'lar daima UTC+3 timezone'ludur.
    Aralik yari-aciktir: [start, end).
    """
    ref = as_of or datetime.now(TR)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=TR)
    ref_day = ref.replace(hour=0, minute=0, second=0, microsecond=0)

    clean = to_ascii(text.lower())

    # 1. ISO tarih: YYYY-MM-DD (orn: 2026-04-15)
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", clean)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        start = datetime(y, m, d, 0, 0, 0, tzinfo=TR)
        return start, start + timedelta(days=1)

    # 2. Belirli bir gun ve ay: "15 nisan 2026" veya "15 nisan"
    # oruntu: 15 nisan (opsiyonel 2026)
    pattern_day_month = r"\b(\d{1,2})\s+(" + "|".join(_MONTHS.keys()) + r")(?:\s+(\d{4}))?\b"
    m_dm = re.search(pattern_day_month, clean)
    if m_dm:
        d = int(m_dm.group(1))
        m = _MONTHS[m_dm.group(2)]
        y = int(m_dm.group(3)) if m_dm.group(3) else ref.year
        try:
            start = datetime(y, m, d, 0, 0, 0, tzinfo=TR)
            # Saat araligi var mi? (orn: "02:00 ile 04:00 arasi" veya "14:00 - 18:00")
            regex_hours = r"\b(\d{1,2})[:.](\d{2})\s*(?:ile|-)\s*(\d{1,2})[:.](\d{2})\b"
            m_hours = re.search(regex_hours, clean)
            if m_hours:
                h1, min1 = int(m_hours.group(1)), int(m_hours.group(2))
                h2, min2 = int(m_hours.group(3)), int(m_hours.group(4))
                return start.replace(hour=h1, minute=min1), start.replace(hour=h2, minute=min2)
            return start, start + timedelta(days=1)
        except ValueError:
            pass

    # 3. Ayin tamami: "nisan 2026" veya "nisan ayi"
    pattern_month = r"\b(" + "|".join(_MONTHS.keys()) + r")(?:\s+ayi|\s+(\d{4}))?\b"
    m_m = re.search(pattern_month, clean)
    if m_m and not m_dm:
        m = _MONTHS[m_m.group(1)]
        y = int(m_m.group(2)) if m_m.group(2) else ref.year
        start = datetime(y, m, 1, 0, 0, 0, tzinfo=TR)
        # sonraki ay basi
        end_y = y + 1 if m == 12 else y
        end_m = 1 if m == 12 else m + 1
        end = datetime(end_y, end_m, 1, 0, 0, 0, tzinfo=TR)
        return start, end

    # 4. Dun gece (onceki gun 20:00 -> bugun 06:00 arasi)
    if ("dun gece" in clean) or ("gece" in clean and "dun" in clean):
        yesterday = ref_day - timedelta(days=1)
        start = yesterday.replace(hour=20, minute=0, second=0)
        end = ref_day.replace(hour=6, minute=0, second=0)
        return start, end

    # 5. Dun (onceki gun tamami)
    if "dun" in clean:
        start = ref_day - timedelta(days=1)
        return start, start + timedelta(days=1)

    # 6. Bugun (bugun tamami)
    if "bugun" in clean:
        return ref_day, ref_day + timedelta(days=1)

    # 7. Gecen hafta (onceki haftanin Pazartesi -> Pazar)
    if "gecen hafta" in clean:
        start = ref_day - timedelta(days=ref_day.weekday() + 7)
        end = start + timedelta(days=7)
        return start, end

    # 8. Bu hafta (Pazartesi -> simdi veya pazar)
    if "bu hafta" in clean:
        start = ref_day - timedelta(days=ref_day.weekday())
        end = start + timedelta(days=7)
        return start, end

    # 9. Gecen ay
    if "gecen ay" in clean:
        this_month = ref_day.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        return last_month, this_month

    # 10. Bu ay
    if "bu ay" in clean:
        start = ref_day.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month

    # 11. Hafta sonu
    if "hafta sonu" in clean:
        saturday = ref_day + timedelta(days=(5 - ref_day.weekday()))
        start = saturday.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=2)
        return start, end

    return None


def extract_time_hint(text: str, *, as_of: datetime | None = None) -> str:
    """Prompt icine eklenebilecek kisa zaman ipucu metni uretir."""
    res = resolve_time_range(text, as_of=as_of)
    if not res:
        return ""
    start, end = res
    return (
        f"[Algilanan Zaman Araligi: start=\"{start.isoformat()}\", end=\"{end.isoformat()}\"]"
    )
