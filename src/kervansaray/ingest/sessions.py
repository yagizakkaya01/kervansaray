"""Session turetme - giris olayini cikis olayiyla eslestirmek (PROJECT_BRIEF S8).

Olaylar teslim sirasinda islenir (zaman sirasi garanti degil - S8 "sirasiz
gelisler"). Her yeni olay icin:

  entry:
    - once: ayni arac/plaka icin YAKIN zamanli bir missing_entry session'i
      var mi (cikisi bu giristen SONRA kaydedilmis)? Varsa geriye doldur
      (sirasi bozuk teslim edilmis giris).
    - yoksa: ayni arac icin acik (current) session varsa -> missing_exit=true
      (onceki kalisin cikisi kacirilmis); ardindan yeni acik session olustur.
  exit:
    - ayni arac/plaka icin acik session varsa -> kapat (exit + duration)
    - yoksa -> missing_entry=true olan bir session olustur

"Acik/current" = exit_event_id IS NULL AND missing_exit IS FALSE.
Eslestirme once vehicle_id (biliniyorsa), yoksa canonical_plate uzerinden.

Sinirlama: cok gecikmis (gun-olcegi) sirasiz teslimler tam mutabakat
edilmez; MERGE_WINDOW ile sinirli.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Direction, Event, Session

# Sirasi bozuk bir girisi mevcut bir missing_entry cikisina baglamak icin
# izin verilen en buyuk kalis suresi.
MERGE_WINDOW = timedelta(days=14)


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


def _find_orphan_exit(db: DbSession, event: Event) -> Session | None:
    """Girisi kacirilmis, cikisi bu giristen sonra kaydedilmis session."""
    stmt = select(Session).where(
        Session.entry_event_id.is_(None),
        Session.missing_entry.is_(True),
        Session.exit_ts >= event.ts,
        Session.exit_ts <= event.ts + MERGE_WINDOW,
    )
    if event.vehicle_id is not None:
        stmt = stmt.where(Session.vehicle_id == event.vehicle_id)
    else:
        stmt = stmt.where(
            Session.vehicle_id.is_(None),
            Session.canonical_plate == event.canonical_plate,
        )
    return db.scalar(stmt.order_by(Session.exit_ts.asc()).limit(1))


def apply_event(db: DbSession, event: Event) -> Session:
    """event'i session modeline uygula ve etkilenen session'i dondur.

    event onceden DB'ye eklenmis ve mutabakati yapilmis olmali (event.id dolu).
    """
    if event.direction == Direction.entry:
        # Sirasi bozuk teslim: cikisi zaten kayitli olan bir konaklamanin girisi.
        orphan = _find_orphan_exit(db, event)
        if orphan is not None:
            orphan.entry_event_id = event.id
            orphan.entry_ts = event.ts
            orphan.missing_entry = False
            orphan.duration_seconds = int((orphan.exit_ts - event.ts).total_seconds())
            db.flush()
            return orphan

        current = _find_current_session(db, event)
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

    current = _find_current_session(db, event)

    # exit
    # Girisi bu cikistan sonra olan bir session'i kapatma (negatif sure) - bu
    # sirasi bozuk bir teslimdir, orphan cikis olarak birak.
    if current is not None and current.entry_ts is not None and current.entry_ts > event.ts:
        current = None

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


def reconcile_vehicle_sessions(
    db: DbSession, vehicle_id: int | None, plates: set[str]
) -> list[Session]:
    """Belirli bir araç veya plaka varyasyonları için session'ları yeniden mutabakat eder.

    Operatör onay kuyruğunda bir olayı onayladığında veya reddettiğinde,
    hatalı okumadan kaynaklanan bölünmüş veya yetim (orphan) session'ları
    kronolojik sırada birleştirir.
    """
    from sqlalchemy import or_

    clean_plates = {p for p in plates if p}
    if vehicle_id is None and not clean_plates:
        return []

    # 1. Mevcut artefakt session'ları sil
    sess_filters = []
    if vehicle_id is not None:
        sess_filters.append(Session.vehicle_id == vehicle_id)
    if clean_plates:
        sess_filters.append(Session.canonical_plate.in_(clean_plates))

    existing = list(db.scalars(select(Session).where(or_(*sess_filters))))
    for s in existing:
        db.delete(s)
    db.flush()

    # 2. İlgili tüm olayları kronolojik sırada al
    ev_filters = []
    if vehicle_id is not None:
        ev_filters.append(Event.vehicle_id == vehicle_id)
    if clean_plates:
        ev_filters.append(Event.canonical_plate.in_(clean_plates))

    events = list(db.scalars(select(Event).where(or_(*ev_filters)).order_by(Event.ts.asc())))

    # 3. apply_event ile baştan sırayla türet
    recreated: list[Session] = []
    for ev in events:
        s = apply_event(db, ev)
        recreated.append(s)

    return recreated

