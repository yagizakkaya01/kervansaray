"""Altin set kosucusu (PROJECT_BRIEF S9).

Faz 3: her altin sorunun BEKLENEN tool cagrisini calistirir ve ciktisini
reference'in dondurdugu (gold_set.jsonl'e donmus) beklenen cevapla
karsilastirir. Tek sayi doner: tool dogrulugu.

  - `decline` sorulari LLM olmadan puanlanamaz -> "Faz 5 bekliyor" olarak
    ayrilir; tool dogruluk oranina girmez.
  - Faz 5'te ikinci bir yol eklenecek: LLM'i calistir, sectigi tool +
    parametreleri altin ile karsilastir, sonra cevabi.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from kervansaray.tools import TOOLS

GOLD_SET = Path(__file__).resolve().parent / "gold_set.jsonl"

_TS_KEYS = ("start", "end", "as_of")


@dataclass
class EvalResult:
    total: int = 0
    scored: int = 0
    correct: int = 0
    deferred: int = 0  # decline -> Faz 5
    by_category: dict[str, list[int]] = field(default_factory=dict)  # cat -> [correct, scored]
    failures: list[dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.scored if self.scored else 0.0

    def summary(self) -> str:
        lines = [
            f"tool dogrulugu: {self.correct}/{self.scored} = {self.accuracy:.3f}",
            f"  (ayrica {self.deferred} 'decline' sorusu Faz 5'i bekliyor)",
            "",
            "kategori bazinda:",
        ]
        for cat, (c, s) in sorted(self.by_category.items()):
            mark = "ok" if c == s else "!!"
            lines.append(f"  [{mark}] {cat:18} {c}/{s}")
        if self.failures:
            lines += ["", "hatalar:"]
            for f in self.failures:
                lines.append(f"  {f['id']} ({f['category']}): beklenen={f['expected']} "
                             f"gelen={f['actual']}")
        return "\n".join(lines)


def load_gold() -> list[dict]:
    with GOLD_SET.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _parse_params(params: dict) -> dict:
    out = dict(params)
    for k in _TS_KEYS:
        if isinstance(out.get(k), str):
            out[k] = datetime.fromisoformat(out[k])
    return out


def _normalise(category: str, expected: dict, result) -> tuple:
    """(expected_norm, actual_norm) - kategoriye gore karsilastirilabilir sekil."""
    r = result
    if "scalar" in expected:
        return expected["scalar"], r.scalar
    if category == "count_by_hour" or category == "count_by_kind":
        exp = {row["group"]: row["value"] for row in expected["rows"]}
        act = {row["group"]: row["value"] for row in r.rows}
        return exp, act
    if category == "list_events":
        act = {"count": len(r.event_ids), "event_ids": sorted(r.event_ids),
               "truncated": r.truncated}
        exp = {"count": expected["count"], "event_ids": sorted(expected["event_ids"]),
               "truncated": expected["truncated"]}
        return exp, act
    if category == "history":
        s = r.scalar
        act = {"known": s["known"], "is_blacklisted": s["is_blacklisted"],
               "event_count": s["event_count"]}
        return expected, act
    if category in ("night_entry", "recurring"):
        act_plates = sorted({row["plate"] for row in r.rows})
        exp = sorted(expected["plates"])
        if category == "recurring":
            return (exp, expected.get("visits")), (act_plates,
                    r.rows[0]["visits"] if r.rows else 0)
        return exp, act_plates
    if category == "blacklist":
        act = {"count": len(r.rows), "plates": sorted({row["plate"] for row in r.rows})}
        return {"count": expected["count"], "plates": sorted(expected["plates"])}, act
    if category == "overstay":
        act_plates = {row["plate"] for row in r.rows}
        return expected["contains_plate"] in act_plates, True
    raise ValueError(f"normalise: bilinmeyen kategori {category}")


def run(db: DbSession) -> EvalResult:
    res = EvalResult()
    for row in load_gold():
        res.total += 1
        cat, tool = row["category"], row["tool"]

        if tool == "decline":
            res.deferred += 1
            continue

        params = _parse_params(row["params"])
        try:
            result = TOOLS[tool](db, **params)
            exp_norm, act_norm = _normalise(cat, row["expected"], result)
            ok = exp_norm == act_norm
        except Exception as exc:  # noqa: BLE001
            ok, exp_norm, act_norm = False, row["expected"], f"HATA: {exc}"

        res.scored += 1
        c, s = res.by_category.get(cat, [0, 0])
        res.by_category[cat] = [c + int(ok), s + 1]
        if ok:
            res.correct += 1
        else:
            res.failures.append(
                {"id": row["id"], "category": cat, "expected": exp_norm, "actual": act_norm}
            )
    return res
