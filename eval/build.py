"""eval/gold_set.jsonl uretir (PROJECT_BRIEF S9).

Sabit sentetik senaryoyu kurar, altin sorulardaki plaka referanslarini cozer,
reference.py ile beklenen cevaplari HESAPLAR ve satir satir yazar. Cikti
commit'lenir; CI checked-in dosyanin yeniden uretilenle ayni oldugunu test
eder (drift guard).

    python -m eval.build         # eval/gold_set.jsonl yaz
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kervansaray.synth import Scenario, generate

from . import reference
from .gold import GOLD, GOLD_DAYS, GOLD_SEED, GOLD_SIZE, GOLD_START, GoldQuestion

OUT = Path(__file__).resolve().parent / "gold_set.jsonl"


def build_scenario() -> Scenario:
    return generate(seed=GOLD_SEED, start=GOLD_START, days=GOLD_DAYS, size=GOLD_SIZE)


def _resolve_plate(scenario: Scenario, ref: str) -> str:
    kind, _, rest = ref.partition(":")
    if kind == "manifest":
        node: Any = scenario.manifest
        for part in rest.split("."):
            node = node[part]
        return node
    if kind == "pop":
        group, idx = rest.split(":")
        return scenario.population.by_kind(group)[int(idx)].plate
    raise ValueError(f"bilinmeyen plate_ref: {ref}")


def resolve(scenario: Scenario, q: GoldQuestion) -> dict:
    params = dict(q.params)
    question = q.question
    if q.plate_ref is not None:
        plate = _resolve_plate(scenario, q.plate_ref)
        question = question.format(plate=plate)
        if params.get("plate") == "$ref":
            params["plate"] = plate
    return {"id": q.id, "category": q.category, "question": question,
            "tool": q.tool, "params": params}


def build() -> list[dict]:
    scenario = build_scenario()
    out = []
    for q in GOLD:
        row = resolve(scenario, q)
        row["expected"] = reference.build_expected(
            scenario, {"category": q.category, "params": row["params"]}
        )
        out.append(row)
    return out


def main() -> None:
    rows = build()
    OUT.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
