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
from sqlalchemy.orm import joinedload

from kervansaray.db.models import Event, Session, Vehicle
from kervansaray.text.plates import canonicalize

from .types import ToolResult


def _resolve_person_to_plate(db: DbSession, person: str) -> ToolResult | str:
    """Kişi adı/unvanından plakaya çözer. Tek eşleşme -> kanonik plaka (str).
    0 veya >1 eşleşme -> erken ToolResult (narrative bunu ele alır)."""
    term = f"%{person.strip()}%"
    matches = list(
        db.execute(
            text(
                "SELECT v.plate, p.name, p.kind::text AS kind, "
                "COALESCE(v.is_blacklisted, FALSE) AS is_blacklisted "
                "FROM vehicles v JOIN persons p ON p.id = v.person_id "
                "WHERE unaccent(p.name) ILIKE unaccent(:t) "
                "OR unaccent(COALESCE(p.title, '')) ILIKE unaccent(:t) "
                "ORDER BY v.plate"
            ),
            {"t": term},
        ).mappings()
    )
    if not matches:
        return ToolResult(
            tool="vehicle_history",
            params={"person": person},
            rows=[],
            scalar={"person_query": person, "matches": 0},
        )
    if len(matches) > 1:
        return ToolResult(
            tool="vehicle_history",
            params={"person": person},
            rows=[
                {"plaka": m["plate"], "kisi": m["name"], "tur": m["kind"],
                 "kara_liste": True if m["is_blacklisted"] else None}
                for m in matches
            ],
            scalar={"person_query": person, "matches": len(matches), "ambiguous": True},
        )
    return canonicalize(matches[0]["plate"])


def vehicle_history(
    db: DbSession, *, plate: str | None = None, person: str | None = None
) -> ToolResult:
    if plate:
        canon = canonicalize(plate)
    elif person:
        resolved = _resolve_person_to_plate(db, person)
        if isinstance(resolved, ToolResult):
            return resolved
        canon = resolved
    else:
        return ToolResult(
            tool="vehicle_history", params={},
            note="plate veya person parametresi zorunludur.",
        )

    vehicle = db.scalar(
        select(Vehicle).options(joinedload(Vehicle.person)).where(Vehicle.plate == canon)
    )

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
    owner_name = vehicle.person.name if vehicle and vehicle.person else None
    owner_kind = str(vehicle.person.kind.value) if vehicle and vehicle.person else None

    return ToolResult(
        tool="vehicle_history",
        params={"plate": canon},
        rows=rows,
        event_ids=[str(e.event_id) for e in events],
        scalar={
            "known": vehicle is not None,
            "owner_name": owner_name,
            "owner_kind": owner_kind,
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
