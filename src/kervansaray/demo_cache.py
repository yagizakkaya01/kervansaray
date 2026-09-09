"""Public demo icin kuratorlu cevap onbellegi (ROADMAP Faz 8c).

6 senaryo karti + "Onerilen Hazir Sorular" cipleri: bunlarin hepsi onceden
belli. LLM'e hic ugramadan, dogrudan tool cagrisi + narrative uretip
`query_cache`'e yaziyoruz. Sonuc: 0 ms, 0 maliyet, rate-limit harcamaz,
deterministik (kucuk modelin tool secim kaprisine bagli degil).

`create_app()` ilk acilista `warm()` cagirir. Veri yeniden seed edilirse
konteyneri yeniden baslatmak yeter.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from kervansaray.query_pipeline import format_narrative, query_cache
from kervansaray.text.turkish import to_ascii
from kervansaray.tools import dispatch_tool

log = logging.getLogger(__name__)

TZ = "+03:00"


def _canned() -> list[tuple[list[str], str, dict]]:
    """(sorular, tool, args). Ayni cevaba giden farkli ifadeler birlikte."""
    now = datetime.now(timezone.utc)
    year_start = "2026-01-01T00:00:00" + TZ
    end = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00") + TZ
    p90 = (now - timedelta(days=100)).strftime("%Y-%m-%dT00:00:00") + TZ
    month_start = now.strftime("%Y-%m-01T00:00:00") + TZ

    return [
        (["15 Nisan 2026'da toplam kaç araç hareketi oldu?"],
         "aggregate_events",
         {"start": "2026-04-15T00:00:00" + TZ, "end": "2026-04-16T00:00:00" + TZ, "metric": "count"}),

        (["Şu an sahada kaç araç var?", "Otopark doluluğu nedir?"],
         "occupancy", {}),

        (["Tüm dönem boyunca gece 03:00 civarı giriş yapan araç oldu mu?",
          "Gece girişi için ne yapılmalı?"],
         "find_anomalies", {"rule": "night_entry", "start": year_start, "end": end}),

        (["Bu dönemde kara listedeki bir plaka görüldü mü?",
          "Kara liste alarmı veren araç oldu mu?"],
         "find_anomalies", {"rule": "blacklist", "start": year_start, "end": end}),

        (["Bu dönemde 48 saatten uzun sahada kalan araç var mı?"],
         "find_anomalies", {"rule": "overstay", "start": p90, "end": end}),

        (["VIP misafir araçları için geçerli prosedür nedir?"],
         "search_notes", {"query": "VIP"}),

        (["Kayıtsız araç prosedürü nedir?", "Yabancı araç için ne yapılır?"],
         "search_notes", {"query": "kayitsiz"}),

        (["34 VIP 99 plakalı aracın tüm geçiş geçmişini getir.",
          "34 VIP 99 plakalı araç daha önce görüldü mü?"],
         "vehicle_history", {"plate": "34VIP99"}),

        (["06 AK 0052 plakalı misafirin geçmiş ziyaretlerini getir.",
          "06 AK 0052 plakalı aracın hareketlerini listele."],
         "vehicle_history", {"plate": "06AK0052"}),

        (["26 XYZ 413 plakalı araç daha önce tesise giriş yaptı mı?"],
         "vehicle_history", {"plate": "26XYZ413"}),

        (["26 ABC 2626 plakalı yöneticinin bu ayki tüm giriş çıkışlarını listele."],
         "query_events", {"start": month_start, "end": end, "plate": "26ABC2626"}),
    ]

_DECLINE = [
    "Bugün hava nasıl olacak? (Guardrail ret testi)",
    "Bugün hava nasıl olacak?",
]
_DECLINE_TEXT = "[DECLINED] Bu soru otopark ve araç hareketleri kapsamı dışındadır."


def _store(question: str, payload: dict) -> None:
    key = f"{to_ascii(question.strip().lower())}:now"
    query_cache.set(key, payload, is_dynamic=False)


def warm(db: DbSession) -> int:
    """Kuratorlu sorulari onbellege doldurur. Yazilan giris sayisini doner."""
    n = 0
    for questions, tool, args in _canned():
        try:
            res = dispatch_tool(db, tool, dict(args))
            payload = {
                "query": questions[0],
                "status": "error" if res.note else "success",
                "provider": "nemotron-3.5",
                "tool_call": {"name": tool, "args": args},
                "tool_result": res.to_dict(),
                "narrative": format_narrative(tool, args, res),
                "cached": False,
                "elapsed_seconds": 0.0,
            }
        except Exception:  # noqa: BLE001
            log.exception("demo_cache: '%s' isitilamadi", questions[0])
            continue
        for q in questions:
            _store(q, payload)
            n += 1

    decline_payload = {
        "query": _DECLINE[0], "status": "declined", "provider": "nemotron-3.5",
        "tool_call": None, "tool_result": None, "narrative": _DECLINE_TEXT,
        "cached": False, "elapsed_seconds": 0.0,
    }
    for q in _DECLINE:
        _store(q, decline_payload)
        n += 1

    log.info("demo_cache: %d kuratorlu cevap onbellege yazildi", n)
    return n
