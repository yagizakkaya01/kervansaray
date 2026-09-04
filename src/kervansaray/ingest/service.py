"""Ingest servisi - dogrulanmis bir EventV1'i depoya yazar.

Akis (PROJECT_BRIEF S6):
    1. Idempotency: event_id daha once gorulduyse -> duplicate (yeni kayit yok)
    2. Plaka mutabakati (reconcile_plate)
    3. Event satirini tipli kolonlara yaz
    4. Session modelini guncelle (apply_event)

Tek transaction; herhangi bir adim patlarsa hicbir sey yazilmaz.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Event, MatchStatus
from kervansaray.events import EventV1

from .reconcile import reconcile_plate
from .sessions import apply_event


@dataclass(frozen=True)
class IngestResult:
    event_row_id: int
    event_id: str
    duplicate: bool
    match_status: MatchStatus
    vehicle_id: int | None
    session_id: int
    session_closed: bool


def ingest_event(db: DbSession, payload: EventV1) -> IngestResult:
    existing = db.scalar(select(Event).where(Event.event_id == payload.dedupe_key))
    if existing is not None:
        # Idempotent tekrar: mevcut kaydin ozetini don, hicbir sey degistirme.
        sess_id, closed = _session_summary(db, existing)
        return IngestResult(
            event_row_id=existing.id,
            event_id=existing.event_id,
            duplicate=True,
            match_status=existing.match_status,
            vehicle_id=existing.vehicle_id,
            session_id=sess_id,
            session_closed=closed,
        )

    rec = reconcile_plate(db, payload.plate)

    event = Event(
        event_id=payload.dedupe_key,
        schema_version=payload.schema_version,
        device_id=payload.device_id,
        camera_id=payload.camera_id,
        ts=payload.ts,
        raw_plate=payload.plate,
        canonical_plate=rec.canonical_plate,
        plate_confidence=payload.plate_confidence,
        direction=payload.direction,
        track_id=payload.track_id,
        crop_ref=payload.crop_ref,
        model_version=payload.model_version,
        vehicle_id=rec.vehicle_id,
        match_status=rec.status,
        match_score=rec.score,
        candidate_vehicle_id=rec.candidate_vehicle_id,
    )
    db.add(event)
    db.flush()

    session = apply_event(db, event)

    return IngestResult(
        event_row_id=event.id,
        event_id=event.event_id,
        duplicate=False,
        match_status=event.match_status,
        vehicle_id=event.vehicle_id,
        session_id=session.id,
        session_closed=session.exit_event_id is not None,
    )


def _session_summary(db: DbSession, event: Event) -> tuple[int, bool]:
    from kervansaray.db.models import Session

    stmt = select(Session).where(
        (Session.entry_event_id == event.id) | (Session.exit_event_id == event.id)
    ).limit(1)
    s = db.scalar(stmt)
    if s is None:
        return (0, False)
    return (s.id, s.exit_event_id is not None)
