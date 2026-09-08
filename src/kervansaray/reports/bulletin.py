"""Gece anomali bülteni üreteci (ROADMAP Faz 6, PROJECT_BRIEF S3.6).

find_anomalies ile son 24 saatteki olayları tarar; yakalanan aykırılıkları
sabah nöbetçi amiri için 3-4 maddelik operasyonel Türkçe özete dönüştürür.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session as DbSession

from kervansaray.db import get_engine, session_scope
from kervansaray.llm import gemini_client
from kervansaray.tools.anomalies import RULES, find_anomalies

TR = timezone(timedelta(hours=3))


def generate_nightly_bulletin(
    db: DbSession,
    as_of: datetime | None = None,
    *,
    client: Any = None,
) -> dict[str, Any]:
    """Son 24 saatlik pencerede anomali taraması yapar ve bülten üretir."""
    ref_time = as_of or datetime.now(tz=TR)
    start_time = ref_time - timedelta(hours=24)

    anomalies_by_rule: dict[str, list[dict[str, Any]]] = {}
    total_count = 0

    for rule in sorted(RULES):
        res = find_anomalies(db, rule=rule, start=start_time, end=ref_time)
        if res.rows:
            anomalies_by_rule[rule] = res.rows
            total_count += len(res.rows)

    date_str = ref_time.strftime("%d.%m.%Y")

    if total_count == 0:
        bulletin_text = (
            f"[{date_str} Sabah Brifingi] Son 24 saatte herhangi bir anomali "
            "tespit edilmedi. Otopark geçişleri ve doluluk olağan akışında."
        )
        return {
            "as_of": ref_time.isoformat(),
            "total_anomalies": 0,
            "anomalies_by_rule": {},
            "bulletin": bulletin_text,
        }

    # Anomali var -> LLM ile 3-4 maddelik operasyonel bülten metni üret
    summary_prompt = (
        f"Sen bir otopark güvenlik danışmanısın. Aşağıdaki {date_str} tarihli anomali listesini "
        "sabah nöbetçi amiri için 3-4 maddelik, çok net, askeri/operasyonel ciddiyette "
        "ve aksiyon odaklı bir Türkçe güvenlik brifingi olarak özetle. "
        "Gereksiz nezaket cümleleri kurma.\n\n"
        f"Anomali Verileri:\n{json.dumps(anomalies_by_rule, ensure_ascii=False, indent=2)}"
    )

    bulletin_text = ""
    llm_module = client or gemini_client

    if hasattr(llm_module, "generate"):
        try:
            llm_resp = llm_module.generate(summary_prompt)
            bulletin_text = llm_resp.text.strip()
        except Exception:  # noqa: BLE001
            bulletin_text = ""

    # LLM yoksa veya hata verdiyse deterministik kural özeti (Ponytail fallback)
    if not bulletin_text:
        lines = [f"[{date_str} Sabah Brifingi - {total_count} Anomali Tespit Edildi]"]
        rule_titles = {
            "blacklist": "Kara Liste İhlali",
            "night_entry": "Gece Girişi (00:00-05:00)",
            "overstay": "Uzun Kalış (48+ Saat)",
            "unregistered_recurring": "Kayıtsız Tekrarlayan Araç",
        }
        for rule, rows in anomalies_by_rule.items():
            title = rule_titles.get(rule, rule)
            plates = ", ".join(r.get("plate", "") for r in rows[:3])
            suffix = "..." if len(rows) > 3 else ""
            lines.append(f"- {title}: {len(rows)} olay ({plates}{suffix})")
        bulletin_text = "\n".join(lines)

    return {
        "as_of": ref_time.isoformat(),
        "total_anomalies": total_count,
        "anomalies_by_rule": anomalies_by_rule,
        "bulletin": bulletin_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kervansaray Gece Anomali Bülteni")
    parser.add_argument("--date", help="ISO formatında tarih (örn: 2026-05-02T08:00:00+03:00)")
    args = parser.parse_args()

    ref = datetime.fromisoformat(args.date) if args.date else None
    engine = get_engine()
    with session_scope(engine) as db:
        res = generate_nightly_bulletin(db, ref)
        print(f"\n=== GÜVENLİK BÜLTENİ ({res['as_of']}) ===")
        print(f"Toplam Anomali: {res['total_anomalies']}")
        print("\n" + res["bulletin"] + "\n")


if __name__ == "__main__":
    main()
