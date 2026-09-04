"""Bilerek kir enjekte et (PROJECT_BRIEF S8).

Temiz bir olay akisi sahada dagilir. Uretici sunlari uretmeli:
  - eksik cikis olaylari (sahadaki bir numarali veri kalite problemi)
  - store-and-forward tekrarlari (ayni event_id)
  - tek karakter bozuk plakalar (fuzzy/pending yolunu calistirir)
  - sirasiz gelisler (cikis, girisinden once teslim edilir)
  - saat kaymasi (bir zaman penceresinde cihaz saati N dk ileri)

Girdi/cikti: teslim sirali GenEvent listesi. EventV1 frozen oldugu icin
degisiklikler model_copy ile yapilir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .events import GenEvent
from .plates import corrupt_one_char
from .rng import SynthRandom


@dataclass(frozen=True)
class DirtConfig:
    missing_exit_rate: float = 0.08
    duplicate_rate: float = 0.03
    ocr_error_rate: float = 0.04
    out_of_order_rate: float = 0.05
    clock_skew_minutes: int = 7
    clock_skew_window_days: int = 2


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


def _clock_skew(r, stream, cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
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


def _missing_exit(r, stream, cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
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


def _ocr_errors(r, stream, cfg: DirtConfig, manifest: dict) -> None:
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


def _out_of_order(r, stream, cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
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


def _duplicates(r, stream, cfg: DirtConfig, manifest: dict) -> list[GenEvent]:
    n = round(len(stream) * cfg.duplicate_rate)
    out = list(stream)
    if not n:
        manifest["duplicate"] = {"events_replayed": 0}
        return out
    # Sondan basa isle ki eklemeler indeksleri kaydirmasin.
    for i in sorted(r.sample(range(len(stream)), n), reverse=True):
        g = stream[i]
        copy = GenEvent(
            payload=g.payload, true_plate=g.true_plate, kind=g.kind,
            role=g.role, visit_ix=g.visit_ix, anomaly=g.anomaly,
            dirt=[*g.dirt, "duplicate"],
        )
        # store-and-forward: birkac olay sonra ayni event_id tekrar teslim edilir
        out.insert(min(len(out), i + r.randint(1, 5)), copy)
    manifest["duplicate"] = {"events_replayed": n}
    return out
