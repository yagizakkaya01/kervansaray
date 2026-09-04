"""Bagimsiz ground-truth oracle (PROJECT_BRIEF S9).

Beklenen cevaplari HESAPLAR - elle etiketlenmez. Mumkun oldugunda sentetik
AKISTAN (ingest'ten once, saf Python) hesaplar; boylece hem ingest hattini
hem tool katmanini bagimsiz olarak dogrular. Yalnizca session'a bagli birkac
soru icin DB'ye bakilir (ikinci SQL formulasyonu - "cross-check").

`build_expected(scenario, question)` -> normalize edilmis beklenen cevap.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from kervansaray.synth import TR, Scenario


def _dedupe(scenario: Scenario) -> list:
    """Store-and-forward tekrarlarini at (ilk teslim kazanir)."""
    seen: set[str] = set()
    out = []
    for g in scenario.stream:
        k = g.payload.dedupe_key
        if k in seen:
            continue
        seen.add(k)
        out.append(g)
    return out


def _in_window(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts < end


def _parse(dt: str) -> datetime:
    return datetime.fromisoformat(dt)


# ---------------------------------------------------------------------------
def build_expected(scenario: Scenario, q: dict) -> Any:
    cat = q["category"]
    p = q["params"]
    fn = _DISPATCH[cat]
    return fn(scenario, p)


def _count(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    n = 0
    for g in _dedupe(scenario):
        e = g.payload
        if not _in_window(e.ts, start, end):
            continue
        if p.get("direction") and e.direction != p["direction"]:
            continue
        n += 1
    return {"scalar": n}


def _count_registered(scenario, p):
    """registered filtresi arac kaydina baglidir - populasyondan hesaplanir."""
    start, end = _parse(p["start"]), _parse(p["end"])
    reg_plates = {
        v.plate for v in scenario.population.vehicles
        if v.registered and v.known and not v.synthetic
    }
    want = p["registered"]
    n = 0
    for g in _dedupe(scenario):
        e = g.payload
        if not _in_window(e.ts, start, end):
            continue
        if p.get("direction") and e.direction != p["direction"]:
            continue
        is_reg = g.true_plate in reg_plates and g.dirt.count("ocr_error") == 0
        if is_reg == want:
            n += 1
    return {"scalar": n}


def _distinct(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    plates = {
        g.payload.plate for g in _dedupe(scenario)
        if _in_window(g.payload.ts, start, end)
    }
    return {"scalar": len(plates)}


def _count_by_hour(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    buckets: dict[int, int] = {}
    for g in _dedupe(scenario):
        e = g.payload
        if not _in_window(e.ts, start, end) or e.direction != "entry":
            continue
        h = e.ts.astimezone(TR).hour
        buckets[h] = buckets.get(h, 0) + 1
    return {"rows": sorted(({"group": str(k), "value": v} for k, v in buckets.items()),
                           key=lambda r: int(r["group"]))}


def _count_by_kind(scenario, p):
    """v_events.person_kind ile gruplama. Eslesmeyen / kisisiz arac -> 'unknown'."""
    start, end = _parse(p["start"]), _parse(p["end"])
    pop = scenario.population
    buckets: dict[str, int] = {}
    for g in _dedupe(scenario):
        e = g.payload
        if not _in_window(e.ts, start, end):
            continue
        spec = pop.find(g.true_plate)
        persisted = spec is not None and spec.known and not spec.synthetic
        matched = persisted and g.dirt.count("ocr_error") == 0
        key = spec.kind if (matched and spec.kind != "unknown") else "unknown"
        buckets[key] = buckets.get(key, 0) + 1
    return {"rows": sorted(({"group": k, "value": v} for k, v in buckets.items()),
                           key=lambda r: r["group"])}


def _list_events(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    rows = []
    for g in _dedupe(scenario):
        e = g.payload
        if not _in_window(e.ts, start, end):
            continue
        if p.get("plate") and e.plate != p["plate"]:
            continue
        if p.get("direction") and e.direction != p["direction"]:
            continue
        rows.append((e.ts, e.dedupe_key))
    rows.sort()
    limit = 50
    truncated = len(rows) > limit
    ids = sorted(k for _, k in rows[:limit])
    return {"count": len(ids), "event_ids": ids, "truncated": truncated}


def _history(scenario, p):
    plate = p["plate"]
    spec = scenario.population.find(plate)
    events = [g for g in _dedupe(scenario) if g.payload.plate == plate]
    return {
        "known": spec is not None and spec.known and not spec.synthetic,
        "is_blacklisted": bool(spec.is_blacklisted) if spec else False,
        "event_count": len(events),
    }


def _night_entry(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    plates = set()
    for g in _dedupe(scenario):
        e = g.payload
        if e.direction != "entry" or not _in_window(e.ts, start, end):
            continue
        if 0 <= e.ts.astimezone(TR).hour < 5:
            plates.add(e.plate)
    return {"plates": sorted(plates)}


def _blacklist(scenario, p):
    start, end = _parse(p["start"]), _parse(p["end"])
    blk = scenario.manifest["anomalies"]["blacklisted"]["plate"]
    events = [
        g for g in _dedupe(scenario)
        if g.true_plate == blk and _in_window(g.payload.ts, start, end)
    ]
    return {"count": len(events), "plates": sorted({g.payload.plate for g in events})}


def _recurring(scenario, p):
    a = scenario.manifest["anomalies"]["recurring_unregistered"]
    start, end = _parse(p["start"]), _parse(p["end"])
    nights = [n for n in a["nights"] if _in_window(_parse(n), start, end)]
    return {"plates": [a["plate"]] if len(nights) >= 3 else [], "visits": len(nights)}


def _overstay(scenario, p):
    """three_day_stay manifesttan; ayrica hala-icerde eski session'lar DB'den
    (cross-check)."""
    three = scenario.manifest["anomalies"]["three_day_stay"]["plate"]
    return {"contains_plate": three}


def _occupancy_now(scenario, p):
    return {"scalar": _replay_occupancy(scenario, as_of=None)}


def _occupancy_asof(scenario, p):
    return {"scalar": _replay_occupancy(scenario, as_of=_parse(p["as_of"]))}


def _decline(scenario, p):
    return {"decline": True}


def _replay_occupancy(scenario: Scenario, *, as_of: datetime | None) -> int:
    """Session mantiginin bagimsiz yeniden uygulanmasi (akistan).

    Teslim sirasi degil, ZAMAN sirasinda oynatir - "belli bir anda kac arac"
    icin dogru referans budur. Bir arac icin yalniz en son giris gecerli
    (onceki = eksik cikis)."""
    # (ts, exit-once) sirasi: ayni an icin cikis girisin sonrasinda islenir.
    events = sorted(_dedupe(scenario), key=lambda g: (g.payload.ts, g.payload.direction == "exit"))
    inside: dict[str, datetime] = {}  # plate -> entry_ts
    for g in events:
        e = g.payload
        if as_of is not None and e.ts > as_of:
            break
        if e.direction == "entry":
            inside[e.plate] = e.ts
        else:
            inside.pop(e.plate, None)
    return len(inside)


_DISPATCH = {
    "count": _count,
    "count_registered": _count_registered,
    "distinct": _distinct,
    "count_by_hour": _count_by_hour,
    "count_by_kind": _count_by_kind,
    "list_events": _list_events,
    "history": _history,
    "night_entry": _night_entry,
    "blacklist": _blacklist,
    "recurring": _recurring,
    "overstay": _overstay,
    "occupancy_now": _occupancy_now,
    "occupancy_asof": _occupancy_asof,
    "decline": _decline,
}
