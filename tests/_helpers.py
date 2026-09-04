"""Test yardimcilari - olay payload'u, arac/kisi seed'i, paylasilan sema kurulumu."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Engine, text

from kervansaray.db import models as _models  # noqa: F401
from kervansaray.db.models import Person, PersonKind, Registration, Vehicle
from kervansaray.db.views import rebuild_schema
from kervansaray.events import EventV1

TR = timezone(timedelta(hours=3))
BASE_TS = datetime(2026, 9, 3, 8, 0, 0, tzinfo=TR)


_TABLES = (
    "sessions", "events", "registrations", "vehicles", "persons", "notes", "daily_summaries",
)


def build_schema(engine: Engine) -> None:
    """Modelden tertemiz sema (create_all + v_events). Testlerin bekledigi durum."""
    rebuild_schema(engine)


def truncate_all(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))


def make_event(
    *,
    plate: str = "34ABC123",
    direction: str = "entry",
    ts: datetime | None = None,
    minutes: int | None = None,
    track_id: int = 1,
    device_id: str = "jetson-01",
    camera_id: str = "entry-1",
    event_id: str | None = None,
    plate_confidence: float = 0.95,
) -> EventV1:
    if ts is None:
        ts = BASE_TS + timedelta(minutes=minutes or 0)
    return EventV1.model_validate(
        {
            "event_id": event_id or str(uuid4()),
            "device_id": device_id,
            "camera_id": camera_id,
            "ts": ts.isoformat(),
            "plate": plate,
            "plate_confidence": plate_confidence,
            "direction": direction,
            "track_id": track_id,
            "model_version": "yolo-plate-v3",
        }
    )


def seed_vehicle(
    db,
    plate: str = "34ABC123",
    *,
    person_name: str | None = None,
    kind: PersonKind = PersonKind.guest,
    blacklisted: bool = False,
    registered: bool = False,
) -> Vehicle:
    person = None
    if person_name:
        person = Person(name=person_name, kind=kind, room_no="101")
        db.add(person)
        db.flush()
    vehicle = Vehicle(
        plate=plate, person_id=person.id if person else None, is_blacklisted=blacklisted
    )
    db.add(vehicle)
    db.flush()
    if registered and person:
        db.add(
            Registration(
                vehicle_id=vehicle.id,
                person_id=person.id,
                valid_from=BASE_TS - timedelta(days=1),
                valid_to=BASE_TS + timedelta(days=7),
            )
        )
        db.flush()
    return vehicle


def load_scenario(db, scenario) -> None:
    """Populasyonu yazar ve tum olay akisini teslim sirasinda ingest eder."""
    from kervansaray.ingest import ingest_event
    from kervansaray.synth.population import persist

    persist(db, scenario.population)
    db.flush()
    for payload in scenario.payloads():
        ingest_event(db, payload)
    db.commit()
