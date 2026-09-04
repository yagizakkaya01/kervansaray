"""Session turetme - giris olayini cikis olayiyla eslestirmek (PROJECT_BRIEF S8).

Olaylar zamanda ileri islenir. Her yeni olay icin:

  entry:
    - ayni arac/plaka icin acik (current) session varsa -> onu missing_exit=true
      yap (onceki kalisin cikisi kacirilmis)
    - yeni acik session olustur
  exit:
    - ayni arac/plaka icin acik session varsa -> kapat (exit + duration)
    - yoksa -> missing_entry=true olan bir session olustur

"Acik/current" = exit_event_id IS NULL AND missing_exit IS FALSE.
Eslestirme once vehicle_id (biliniyorsa), yoksa canonical_plate uzerinden.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Direction, Event, Session


def _find_current_session(db: DbSession, event: Event) -> Session | None:
    stmt = select(Session).where(
        Session.exit_event_id.is_(None),
        Session.missing_exit.is_(False),
    )
    if event.vehicle_id is not None:
        stmt = stmt.where(Session.vehicle_id == event.vehicle_id)
    else:
        stmt = stmt.where(
            Session.vehicle_id.is_(None),
            Session.canonical_plate == event.canonical_plate,
        )
    stmt = stmt.order_by(Session.entry_ts.desc().nullslast()).limit(1)
    return db.scalar(stmt)


def apply_event(db: DbSession, event: Event) -> Session:
    """event'i session modeline uygula ve etkilenen session'i dondur.

    event onceden DB'ye eklenmis ve mutabakati yapilmis olmali (event.id dolu).
    """
    current = _find_current_session(db, event)

    if event.direction == Direction.entry:
        if current is not None:
            current.missing_exit = True
        new = Session(
            vehicle_id=event.vehicle_id,
            canonical_plate=event.canonical_plate,
            entry_event_id=event.id,
            entry_ts=event.ts,
        )
        db.add(new)
        db.flush()
        return new

    # exit
    if current is not None:
        current.exit_event_id = event.id
        current.exit_ts = event.ts
        if current.entry_ts is not None:
            current.duration_seconds = int((event.ts - current.entry_ts).total_seconds())
        db.flush()
        return current

    orphan = Session(
        vehicle_id=event.vehicle_id,
        canonical_plate=event.canonical_plate,
        exit_event_id=event.id,
        exit_ts=event.ts,
        missing_entry=True,
    )
    db.add(orphan)
    db.flush()
    return orphan
