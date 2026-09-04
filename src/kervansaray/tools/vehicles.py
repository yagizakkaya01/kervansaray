"""vehicle_history + occupancy (PROJECT_BRIEF S3.2, S8).

occupancy = "su an sahada kac arac?" - S8'in headline sorusu. Acik session
(exit_event_id NULL AND missing_exit FALSE) sayilir.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Event, Session, Vehicle
from kervansaray.text.plates import canonicalize

from .types import ToolResult


def vehicle_history(db: DbSession, *, plate: str) -> ToolResult:
    canon = canonicalize(plate)
    vehicle = db.scalar(select(Vehicle).where(Vehicle.plate == canon))

    events = list(
        db.scalars(
            select(Event).where(Event.canonical_plate == canon).order_by(Event.ts.asc())
        )
    )
    sessions = list(
        db.scalars(
            select(Session)
            .where(Session.canonical_plate == canon)
            .order_by(Session.entry_ts.asc().nullsfirst())
        )
    )

    rows = [
        {
            "event_id": str(e.event_id), "ts": e.ts.isoformat(), "direction": str(e.direction),
            "match_status": str(e.match_status), "raw_plate": e.raw_plate,
        }
        for e in events
    ]
    session_rows = [
        {
            "entry_ts": s.entry_ts.isoformat() if s.entry_ts else None,
            "exit_ts": s.exit_ts.isoformat() if s.exit_ts else None,
            "duration_seconds": s.duration_seconds,
            "missing_entry": s.missing_entry, "missing_exit": s.missing_exit,
            "currently_inside": s.is_current,
        }
        for s in sessions
    ]
    return ToolResult(
        tool="vehicle_history",
        params={"plate": canon},
        rows=rows,
        event_ids=[str(e.event_id) for e in events],
        scalar={
            "known": vehicle is not None,
            "vehicle_label": vehicle.label if vehicle else None,
            "is_blacklisted": bool(vehicle.is_blacklisted) if vehicle else False,
            "event_count": len(events),
            "session_count": len(sessions),
            "sessions": session_rows,
        },
    )


def occupancy(db: DbSession, *, as_of: datetime | None = None) -> ToolResult:
    """Belirtilen ana (yoksa simdi) gore sahada oldugu bilinen araclar.

    as_of verilirse: entry_ts <= as_of olan ve (exit_ts NULL veya exit_ts > as_of)
    olan session'lar. missing_exit olanlar sayilmaz (gercekten acik degil).
    """
    stmt = select(Session).where(Session.missing_exit.is_(False))
    if as_of is None:
        stmt = stmt.where(Session.exit_event_id.is_(None))
    else:
        stmt = stmt.where(
            Session.entry_ts.isnot(None),
            Session.entry_ts <= as_of,
            (Session.exit_ts.is_(None)) | (Session.exit_ts > as_of),
        )
    sessions = list(db.scalars(stmt.order_by(Session.entry_ts.asc())))
    rows = [
        {
            "plate": s.canonical_plate,
            "entry_ts": s.entry_ts.isoformat() if s.entry_ts else None,
            "vehicle_id": s.vehicle_id,
        }
        for s in sessions
    ]
    return ToolResult(
        tool="occupancy",
        params={"as_of": as_of.isoformat() if as_of else None},
        rows=rows,
        scalar=len(rows),
    )
