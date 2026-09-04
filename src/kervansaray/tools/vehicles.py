"""vehicle_history + occupancy (PROJECT_BRIEF S3.2, S8).

occupancy = "su an / belli bir anda sahada kac arac?" - S8'in headline sorusu.
Nokta-zamanli tanim: bir plakanin `as_of`'a kadarki SON olayi `entry` ise
arac iceridedir. Bu tanim eksik-cikis kirini (S8) oldugu gibi yansitir ve
sessions tablosunun son-durum bayraklarina bagli kalmaz.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, text
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
    """as_of'a (yoksa: tum kayit) kadar son olayi 'entry' olan plakalar."""
    where = "WHERE ts <= :as_of" if as_of is not None else ""
    params = {"as_of": as_of} if as_of is not None else {}
    sql = text(  # noqa: S608 - where sabit
        f"""
        SELECT plate, entry_ts FROM (
            SELECT DISTINCT ON (plate) plate, direction, ts AS entry_ts
            FROM v_events {where}
            ORDER BY plate, ts DESC, (direction = 'exit') DESC
        ) t
        WHERE direction = 'entry'
        ORDER BY entry_ts
        """
    )
    rows = [
        {"plate": r.plate, "entry_ts": r.entry_ts.isoformat()}
        for r in db.execute(sql, params)
    ]
    return ToolResult(
        tool="occupancy",
        params={"as_of": as_of.isoformat() if as_of else None},
        rows=rows,
        scalar=len(rows),
    )
