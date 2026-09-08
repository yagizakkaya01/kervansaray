"""Kir ve anomali enjeksiyonu (PROJECT_BRIEF S8).

Enjekte edilen kirler:
  - eksik cikis olaylari
  - store-and-forward tekrarlari
  - tek karakter bozuk plakalar (OCR)
  - sirasiz gelisler
  - saat kaymasi

Enjekte edilen anomaliler:
  - uc gun kalan arac (three_day_stay)
  - bes gece ust uste gelen kayitsiz arac (recurring_unregistered)
  - 03:00 girisi (night_entry)
  - kara listedeki plaka (blacklisted)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .generator import GenEvent, SynthRandom
    from .population import Population, Visit


@dataclass(frozen=True)
class DirtConfig:
    missing_exit_rate: float = 0.08
    duplicate_rate: float = 0.03
    ocr_error_rate: float = 0.04
    out_of_order_rate: float = 0.05
    clock_skew_minutes: int = 7
    clock_skew_window_days: int = 2


# --- 1. Kir Enjeksiyonu ------------------------------------------------
def inject(
    rng: SynthRandom, stream: list[GenEvent], cfg: DirtConfig
) -> tuple[list[GenEvent], dict]:
    r = rng.for_stream("dirt")
    manifest: dict = {}

    stream = _clock_skew(r, stream, cfg, manifest)
    stream = _missing_exit(r, stream, cfg, manifest)
    _ocr_errors(r, stream, cfg, manifest)
    stream.sort(key=lambda g: g.ts)
    stream = _out_of_order(r, stream, cfg, manifest)
    stream = _duplicates(r, stream, cfg, manifest)

    manifest["total_delivered"] = len(stream)
    return stream, manifest


def _clock_skew(r, stream: list[GenEvent], cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
    if not stream:
        return stream
    lo, hi = stream[0].ts, stream[-1].ts
    span = (hi - lo).days
    win_start = (lo + timedelta(days=int(span * 0.6))).replace(hour=0, minute=0, second=0)
    win_end = win_start + timedelta(days=cfg.clock_skew_window_days)
    delta = timedelta(minutes=cfg.clock_skew_minutes)
    n = 0
    for g in stream:
        if win_start <= g.ts < win_end:
            g.payload = g.payload.model_copy(update={"ts": g.ts + delta})
            g.dirt.append("clock_skew")
            n += 1
    manifest["clock_skew"] = {
        "window_start": win_start.isoformat(), "window_end": win_end.isoformat(),
        "minutes": cfg.clock_skew_minutes, "events_affected": n,
    }
    return stream


def _missing_exit(r, stream: list[GenEvent], cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
    by_visit: dict[int, list[GenEvent]] = {}
    for g in stream:
        by_visit.setdefault(g.visit_ix, []).append(g)

    candidates = [
        ix for ix, evs in by_visit.items()
        if len(evs) == 2 and all(e.anomaly is None for e in evs)
    ]
    r.shuffle(candidates)
    drop_n = round(len(candidates) * cfg.missing_exit_rate)
    dropped = set(candidates[:drop_n])

    kept = []
    dropped_info = []
    for g in stream:
        if g.visit_ix in dropped and g.role == "exit":
            dropped_info.append({"plate": g.true_plate, "entry_or_exit": "exit dropped"})
            continue
        kept.append(g)
    manifest["missing_exit"] = {"visits_affected": len(dropped), "sample": dropped_info[:5]}
    return kept


def _ocr_errors(r, stream: list[GenEvent], cfg: DirtConfig, manifest: dict) -> None:
    from .generator import corrupt_one_char

    pool = [g for g in stream if g.anomaly is None]
    r.shuffle(pool)
    n = round(len(pool) * cfg.ocr_error_rate)
    for g in pool[:n]:
        bad = corrupt_one_char(r, g.payload.plate)
        g.payload = g.payload.model_copy(
            update={"plate": bad, "plate_confidence": round(r.uniform(0.55, 0.78), 3)}
        )
        g.dirt.append("ocr_error")
    manifest["ocr_error"] = {"events_affected": n}


def _out_of_order(r, stream: list[GenEvent], cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
    by_visit: dict[int, list[GenEvent]] = {}
    for g in stream:
        by_visit.setdefault(g.visit_ix, []).append(g)

    pairs = [
        evs for evs in by_visit.values()
        if len(evs) == 2
        and {e.role for e in evs} == {"entry", "exit"}
        and all(e.anomaly is None for e in evs)
    ]
    r.shuffle(pairs)
    n = round(len(pairs) * cfg.out_of_order_rate)

    swapped = 0
    for evs in pairs[:n]:
        entry = next(e for e in evs if e.role == "entry")
        exit_ = next(e for e in evs if e.role == "exit")
        ei = next(i for i, g in enumerate(stream) if g is entry)
        xi = next(i for i, g in enumerate(stream) if g is exit_)
        if xi > ei:
            stream.insert(ei, stream.pop(xi))
            entry.dirt.append("out_of_order")
            exit_.dirt.append("out_of_order")
            swapped += 1
    manifest["out_of_order"] = {"visits_affected": swapped}
    return stream


def _duplicates(r, stream: list[GenEvent], cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
    from .generator import GenEvent

    n = round(len(stream) * cfg.duplicate_rate)
    out = list(stream)
    if not n:
        manifest["duplicate"] = {"events_replayed": 0}
        return out
    for i in sorted(r.sample(range(len(stream)), n), reverse=True):
        g = stream[i]
        copy = GenEvent(
            payload=g.payload, true_plate=g.true_plate, kind=g.kind,
            role=g.role, visit_ix=g.visit_ix, anomaly=g.anomaly,
            dirt=[*g.dirt, "duplicate"],
        )
        out.insert(min(len(out), i + r.randint(1, 5)), copy)
    manifest["duplicate"] = {"events_replayed": n}
    return out


# --- 2. Anomali Enjeksiyonu -------------------------------------------
def inject_anomalies(rng: SynthRandom, pop: Population, visits: list[Visit]) -> dict:
    from .generator import random_plate
    from .population import VehicleSpec, Visit, _time_of_day

    r = rng.for_stream("anomalies")
    mid = pop.period_start + (pop.period_end - pop.period_start) / 2
    manifest: dict = {}

    # 1. Uc gun (3 gece) kalan misafir.
    three = VehicleSpec(
        plate=random_plate(r), kind="guest", person_name="Uzun Konaklama",
        room_no="512", registered=True,
        reg_from=pop.period_start - timedelta(days=1),
        reg_to=pop.period_end + timedelta(days=1),
        anomaly="three_day_stay",
    )
    pop.vehicles.append(three)
    entry = _time_of_day(mid, 15.0, r)
    leave = _time_of_day(mid + timedelta(days=3), 11.0, r)
    visits.append(Visit(three, entry, leave))
    manifest["three_day_stay"] = {
        "plate": three.plate, "entry_ts": entry.isoformat(), "exit_ts": leave.isoformat(),
        "nights": 3,
    }

    # 2. Bes gece ust uste gelen kayitsiz arac.
    recurring = VehicleSpec(
        plate=random_plate(r), kind="unknown", known=False,
        anomaly="recurring_unregistered",
    )
    pop.vehicles.append(recurring)
    span = (pop.period_end - pop.period_start).days
    start_day = pop.period_start + timedelta(days=int(span * 0.3))
    nights = []
    for i in range(5):
        d = start_day + timedelta(days=i)
        e = _time_of_day(d, 21.0 + r.random(), r)
        x = _time_of_day(d + timedelta(days=1), 6.0 + r.random(), r)
        visits.append(Visit(recurring, e, x))
        nights.append(e.isoformat())
    manifest["recurring_unregistered"] = {"plate": recurring.plate, "nights": nights}

    # 3. 03:00 girisi (alisilmadik saat).
    night = VehicleSpec(
        plate=random_plate(r), kind="unknown", known=False, anomaly="night_entry"
    )
    pop.vehicles.append(night)
    d = pop.period_start + timedelta(days=int((pop.period_end - pop.period_start).days * 0.6))
    e = d.replace(hour=3, minute=r.randint(0, 40), second=r.randint(0, 59), microsecond=0)
    x = e + timedelta(hours=r.randint(1, 4))
    visits.append(Visit(night, e, x))
    manifest["night_entry"] = {"plate": night.plate, "entry_ts": e.isoformat()}

    # 4. Kara listedeki plaka.
    unknowns = [v for v in pop.by_kind("unknown") if v.anomaly is None and not v.synthetic]
    blk = unknowns[0] if unknowns else pop.vehicles[0]
    blk.is_blacklisted = True
    blk.anomaly = "blacklisted"
    appears = sorted(v.entry_ts for v in visits if v.spec is blk)
    if not appears:
        d = _time_of_day(mid + timedelta(days=1), 19.0, r)
        visits.append(Visit(blk, d, d + timedelta(hours=2)))
        appears = [d]
    manifest["blacklisted"] = {
        "plate": blk.plate,
        "first_seen": appears[0].isoformat(),
        "appearances": len(appears),
    }

    visits.sort(key=lambda v: v.entry_ts)
    return manifest
