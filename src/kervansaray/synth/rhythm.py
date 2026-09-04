"""Gercekci giris/cikis ritmi (PROJECT_BRIEF S8).

Kir ve anomaliler ENJEKTE EDILMEDEN once "temiz" konaklama takvimini uretir:
  - misafir: ogleden sonra check-in piki (13:00-20:00), sabah checkout
  - personel: vardiya desenleri (sabah / aksam / gece)
  - tedarikci: hafta ici gunduz, kisa ziyaret
  - bilinmeyen: seyrek, kisa, cogunlukla gunduz
  - hafta ici / hafta sonu farki
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .population import Population, VehicleSpec
from .rng import SynthRandom

# Tam scripted ziyareti olan anomaliler - rhythm bunlari atlar.
_SCRIPTED = frozenset({"three_day_stay", "recurring_unregistered", "night_entry"})

_SHIFTS = {
    "morning": (time(7, 0), time(15, 0)),
    "evening": (time(15, 0), time(23, 0)),
    "night": (time(23, 0), time(7, 0)),  # ertesi gune tasar
}


@dataclass
class Visit:
    spec: VehicleSpec
    entry_ts: datetime
    exit_ts: datetime | None  # None = donem sonunda hala iceride


def _at(day: datetime, t: time, jitter_min: int, r) -> datetime:
    base = day.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    return base + timedelta(minutes=r.randint(-jitter_min, jitter_min))


def _tri(r, lo: float, mode: float, hi: float) -> float:
    return r.triangular(lo, mode, hi)


def _time_of_day(day: datetime, hours: float, r) -> datetime:
    h = int(hours)
    m = int((hours - h) * 60)
    return day.replace(hour=min(h, 23), minute=m, second=r.randint(0, 59), microsecond=0)


def _days(start: datetime, end: datetime):
    d = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while d < end:
        yield d
        d += timedelta(days=1)


def build_visits(rng: SynthRandom, pop: Population) -> list[Visit]:
    visits: list[Visit] = []
    visits += _guest_visits(rng.for_stream("rhythm.guest"), pop)
    visits += _staff_visits(rng.for_stream("rhythm.staff"), pop)
    visits += _vendor_visits(rng.for_stream("rhythm.vendor"), pop)
    visits += _unknown_visits(rng.for_stream("rhythm.unknown"), pop)
    visits.sort(key=lambda v: v.entry_ts)
    return visits


def _guest_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    span_days = (pop.period_end - pop.period_start).days
    for spec in pop.by_kind("guest"):
        if spec.anomaly in _SCRIPTED:
            continue
        n_stays = r.choices((1, 2, 3, 4), weights=(45, 30, 18, 7))[0]
        used: list[tuple[datetime, datetime]] = []
        for _ in range(n_stays):
            for _try in range(6):
                offset = r.randint(0, max(0, span_days - 1))
                check_in_day = pop.period_start + timedelta(days=offset)
                # hafta sonu check-in biraz daha olasi
                if check_in_day.weekday() >= 4 and r.random() < 0.35:
                    pass
                nights = r.choices((1, 2, 3, 4, 5), weights=(30, 32, 20, 12, 6))[0]
                entry = _time_of_day(check_in_day, _tri(r, 13.0, 16.0, 20.0), r)
                exit_day = check_in_day + timedelta(days=nights)
                leave = _time_of_day(exit_day, _tri(r, 8.0, 10.5, 12.5), r)
                if any(entry < b and leave > a for a, b in used):
                    continue
                used.append((entry, leave))
                inside = leave <= pop.period_end
                out.append(Visit(spec, entry, leave if inside else None))
                break
    return out


def _staff_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    for spec in pop.by_kind("staff"):
        if spec.anomaly in _SCRIPTED:
            continue
        shift = r.choice(list(_SHIFTS))
        start_t, end_t = _SHIFTS[shift]
        for day in _days(pop.period_start, pop.period_end):
            weekend = day.weekday() >= 5
            if r.random() > (0.30 if weekend else 0.62):
                continue
            entry = _at(day, start_t, 25, r)
            end_day = day + timedelta(days=1) if shift == "night" else day
            leave = _at(end_day, end_t, 45, r)
            inside = leave <= pop.period_end
            out.append(Visit(spec, entry, leave if inside else None))
    return out


def _vendor_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    for spec in pop.by_kind("vendor"):
        if spec.anomaly in _SCRIPTED:
            continue
        for day in _days(pop.period_start, pop.period_end):
            if day.weekday() >= 5 or r.random() > 0.35:
                continue
            entry = _time_of_day(day, _tri(r, 8.0, 11.0, 15.0), r)
            leave = entry + timedelta(minutes=r.randint(20, 100))
            out.append(Visit(spec, entry, leave if leave <= pop.period_end else None))
    return out


def _unknown_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    span_days = max(1, (pop.period_end - pop.period_start).days)
    for spec in pop.by_kind("unknown"):
        if spec.anomaly in _SCRIPTED:
            continue
        for _ in range(r.choices((1, 2, 3), weights=(55, 33, 12))[0]):
            day = pop.period_start + timedelta(days=r.randrange(span_days))
            entry = _time_of_day(day, _tri(r, 7.0, 13.0, 21.0), r)
            leave = entry + timedelta(minutes=r.randint(15, 180))
            out.append(Visit(spec, entry, leave if leave <= pop.period_end else None))
    return out
