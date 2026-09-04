"""Ziyaretleri EventV1 olaylarina cevirir (kir henuz yok).

Her ziyaret -> giris olayi (+ cikis olayi, exit_ts varsa). track_id gercek
ByteTrack gibi her gun sifirdan sayar. event_id deterministik uretilir
(tohum + sayac) - idempotency testleri ve altin set bunu gerektirir.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from kervansaray.events import EventV1
from kervansaray.text.plates import canonicalize

from .rhythm import Visit
from .rng import SynthRandom

DEVICE_ID = "gate-1"
MODEL_VERSION = "yolo-plate-v3"


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
