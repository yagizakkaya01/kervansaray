"""Sentetik senaryo uretici - populasyon + olay akisi + manifest.

Tek giris noktasi: `generate(...)`. Deterministik: ayni parametreler ayni
akisi verir (altin set Faz 3 buna dayanir).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from . import anomalies, dirt, events, population, rhythm
from .dirt import DirtConfig
from .events import GenEvent
from .population import Population
from .rng import SynthRandom

TR = timezone(timedelta(hours=3))  # Turkiye, DST yok

DEFAULT_SIZE = 200
DEFAULT_DAYS = 90


@dataclass
class Scenario:
    population: Population
    stream: list[GenEvent]
    manifest: dict

    def payloads(self) -> list:
        return [g.payload for g in self.stream]


def _normalize_start(start: date | datetime) -> datetime:
    if isinstance(start, datetime):
        base = start
    else:
        base = datetime(start.year, start.month, start.day)
    if base.tzinfo is None:
        base = base.replace(tzinfo=TR)
    return base.replace(hour=0, minute=0, second=0, microsecond=0)


def generate(
    *,
    seed: int = 42,
    start: date | datetime | None = None,
    days: int = DEFAULT_DAYS,
    size: int = DEFAULT_SIZE,
    dirt_config: DirtConfig | None = None,
) -> Scenario:
    rng = SynthRandom(seed)
    period_start = _normalize_start(start or (datetime.now(TR) - timedelta(days=days)))
    period_end = period_start + timedelta(days=days)
    cfg = dirt_config or DirtConfig()

    pop = population.build_population(
        rng, size=size, period_start=period_start, period_end=period_end
    )
    visits = rhythm.build_visits(rng, pop)
    anomaly_manifest = anomalies.inject(rng, pop, visits)
    clean = events.build_events(rng, visits)
    stream, dirt_manifest = dirt.inject(rng, clean, cfg)

    manifest = {
        "seed": seed,
        "period_start": period_start.astimezone(UTC).isoformat(),
        "period_end": period_end.astimezone(UTC).isoformat(),
        "days": days,
        "population_size": len(pop.vehicles),
        "synthetic_plates": [v.plate for v in pop.vehicles if v.synthetic],
        "counts": _counts(pop, visits, stream),
        "anomalies": anomaly_manifest,
        "dirt": dirt_manifest,
    }
    return Scenario(population=pop, stream=stream, manifest=manifest)


def _counts(pop: Population, visits: list[rhythm.Visit], stream: list[GenEvent]) -> dict:
    kinds = Counter(v.spec.kind for v in visits)
    unique_ids = {g.payload.dedupe_key for g in stream}
    roles = Counter(g.role for g in stream)
    kind_names = ("guest", "staff", "vendor", "unknown")
    return {
        "vehicles_by_kind": {k: len(pop.by_kind(k)) for k in kind_names},
        "visits": len(visits),
        "visits_by_kind": dict(kinds),
        "events_delivered": len(stream),
        "events_unique": len(unique_ids),
        "entries": roles.get("entry", 0),
        "exits": roles.get("exit", 0),
        "distinct_plates_seen": len({g.payload.plate for g in stream}),
    }
