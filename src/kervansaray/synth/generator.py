"""Sentetik olay ve senaryo uretimi: RNG, plaka, event fabrikasi, senaryo ve loader."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from random import Random

import requests

from kervansaray.events import EventV1
from kervansaray.text.plates import canonicalize

from .dirt import DirtConfig, inject_anomalies
from .dirt import inject as inject_dirt
from .population import Population, Visit, build_population, build_visits

TR = timezone(timedelta(hours=3))  # Turkiye, DST yok

DEFAULT_SIZE = 200
DEFAULT_DAYS = 90
DEVICE_ID = "gate-1"
MODEL_VERSION = "yolo-plate-v3"

# Turk plakalarinda kullanilan harfler (Q/W/X ve Turkce'ye ozgu harfler yok).
PLATE_LETTERS = "ABCDEFGHIJKLMNOPRSTUVYZ"

# (harf, rakam) - text.plates._VALID_SHAPES ile ayni tutulmali.
_SHAPES = ((1, 4), (2, 3), (2, 4), (3, 2), (3, 3))


# --- 1. Deterministik RNG ---------------------------------------------
class SynthRandom:
    """Deterministik, akis-bazli rastgelelik."""

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def for_stream(self, name: str) -> Random:
        h = hashlib.sha256(f"{self.seed}:{name}".encode()).digest()
        return Random(int.from_bytes(h[:8], "big"))


# --- 2. Plaka Uretimi -------------------------------------------------
def _letters(rng: Random, n: int) -> str:
    return "".join(rng.choice(PLATE_LETTERS) for _ in range(n))


def _digits(rng: Random, n: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


def random_plate(rng: Random, *, province: int | None = None, synthetic: bool = False) -> str:
    """Kanonik formda ('34ABC123') tek bir plaka uretir."""
    if province is None:
        province = rng.randint(82, 99) if synthetic else rng.randint(1, 81)
    n_letters, n_digits = rng.choice(_SHAPES)
    return f"{province:02d}{_letters(rng, n_letters)}{_digits(rng, n_digits)}"


def unique_plates(
    rng: Random, count: int, *, synthetic_ratio: float = 0.0
) -> list[str]:
    """`count` adet benzersiz plaka. synthetic_ratio kadari 82-99 il kodlu."""
    n_synth = round(count * synthetic_ratio)
    out: set[str] = set()
    while len(out) < count:
        want_synth = len(out) < n_synth
        out.add(random_plate(rng, synthetic=want_synth))
    return sorted(out)


def corrupt_one_char(rng: Random, plate: str) -> str:
    """Plakada tek karakteri komsu bir karakterle degistirir (OCR hatasi taklidi)."""
    idx = rng.randrange(2, len(plate))
    ch = plate[idx]
    if ch.isdigit():
        repl = str((int(ch) + rng.choice((-1, 1))) % 10)
    else:
        pos = PLATE_LETTERS.index(ch) if ch in PLATE_LETTERS else 0
        repl = PLATE_LETTERS[(pos + rng.choice((-1, 1))) % len(PLATE_LETTERS)]
    return plate[:idx] + repl + plate[idx + 1 :]


# --- 3. GenEvent Fabrikasi --------------------------------------------
@dataclass
class GenEvent:
    payload: EventV1
    true_plate: str          # kanonik gercek plaka (spec.plate)
    kind: str                # ziyaret turu: guest/staff/vendor/unknown
    role: str                # "entry" | "exit"
    visit_ix: int
    anomaly: str | None = None
    dirt: list[str] = field(default_factory=list)

    @property
    def ts(self) -> datetime:
        return self.payload.ts


def _uuid(r) -> str:
    return str(uuid.UUID(int=r.getrandbits(128)))


def build_events(rng: SynthRandom, visits: list[Visit]) -> list[GenEvent]:
    r = rng.for_stream("events")
    out: list[GenEvent] = []
    track_by_day: dict[str, int] = {}

    def next_track(ts: datetime) -> int:
        key = ts.strftime("%Y-%m-%d")
        track_by_day[key] = track_by_day.get(key, 0) + 1
        return track_by_day[key]

    for ix, v in enumerate(visits):
        canon = canonicalize(v.spec.plate)
        for role, ts, cam in _endpoints(v):
            out.append(
                GenEvent(
                    payload=EventV1(
                        event_id=_uuid(r),
                        device_id=DEVICE_ID,
                        camera_id=cam,
                        ts=ts,
                        plate=canon,
                        plate_confidence=round(r.uniform(0.86, 0.99), 3),
                        direction=role,
                        track_id=next_track(ts),
                        model_version=MODEL_VERSION,
                    ),
                    true_plate=canon,
                    kind=v.spec.kind,
                    role=role,
                    visit_ix=ix,
                    anomaly=v.spec.anomaly,
                )
            )
    out.sort(key=lambda g: g.ts)
    return out


def _endpoints(v: Visit):
    yield ("entry", v.entry_ts, "entry-cam")
    if v.exit_ts is not None:
        yield ("exit", v.exit_ts, "exit-cam")


# --- 4. Senaryo Calistirici -------------------------------------------
@dataclass
class Scenario:
    population: Population
    stream: list[GenEvent]
    manifest: dict

    def payloads(self) -> list[EventV1]:
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

    pop = build_population(rng, size=size, period_start=period_start, period_end=period_end)
    visits = build_visits(rng, pop)
    anomaly_manifest = inject_anomalies(rng, pop, visits)
    clean = build_events(rng, visits)
    stream, dirt_manifest = inject_dirt(rng, clean, cfg)

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


def _counts(pop: Population, visits: list[Visit], stream: list[GenEvent]) -> dict:
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


# --- 5. Loader (Dosya / DB / API) -------------------------------------
@dataclass
class PostStats:
    created: int = 0
    duplicate: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.duplicate + self.failed


def write_jsonl(path: str | Path, payloads: Iterable[EventV1]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for ev in payloads:
            f.write(ev.model_dump_json() + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> list[EventV1]:
    with Path(path).open(encoding="utf-8") as f:
        return [EventV1.model_validate_json(line) for line in f if line.strip()]


def post_stream(
    base_url: str,
    payloads: Iterable[EventV1],
    *,
    timeout: float = 10.0,
    on_progress: Callable[[int, PostStats], None] | None = None,
    progress_every: int = 250,
) -> PostStats:
    url = base_url.rstrip("/") + "/events"
    stats = PostStats()
    session = requests.Session()
    for i, ev in enumerate(payloads, start=1):
        try:
            resp = session.post(
                url,
                data=ev.model_dump_json(),
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 201:
                stats.created += 1
            elif resp.status_code == 200:
                stats.duplicate += 1
            else:
                stats.failed += 1
                if len(stats.errors) < 10:
                    stats.errors.append(f"{resp.status_code}: {resp.text[:180]}")
        except requests.RequestException as exc:
            stats.failed += 1
            if len(stats.errors) < 10:
                stats.errors.append(str(exc))
        if on_progress and i % progress_every == 0:
            on_progress(i, stats)
    return stats


def dump_manifest(path: str | Path, manifest: dict) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
