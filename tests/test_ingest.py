"""Ingest servisi - Faz 1 cikis kriterleri (PROJECT_BRIEF S6/S8).

- elle atilan olay akisi DB'ye dogru dusuyor
- ayni event_id ile tekrar -> reddediliyor (idempotency)
- session'lar olusuyor (giris/cikis eslesmesi, eksik cikis, eksik giris)
"""
from sqlalchemy import func, select

from kervansaray.db.models import Event, MatchStatus, Session
from kervansaray.ingest import ingest_event
from tests._helpers import make_event, seed_vehicle


def test_event_lands_with_typed_columns(db):
    seed_vehicle(db, "34ABC123", person_name="Yagiz Akkaya", registered=True)
    res = ingest_event(db, make_event(plate="34 abc 123", direction="entry"))
    db.commit()

    row = db.get(Event, res.event_row_id)
    assert row.canonical_plate == "34ABC123"
    assert row.raw_plate == "34ABC123"
    assert row.match_status == MatchStatus.exact
    assert row.vehicle_id is not None
    assert row.ts.utcoffset() is not None  # tz korunuyor


def test_duplicate_event_id_rejected(db):
    ev = make_event()
    first = ingest_event(db, ev)
    db.commit()
    second = ingest_event(db, ev)  # ayni event_id
    db.commit()

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.event_row_id == first.event_row_id
    assert db.scalar(select(func.count()).select_from(Event)) == 1


def test_entry_then_exit_forms_closed_session(db):
    seed_vehicle(db, "34ABC123")
    ingest_event(db, make_event(direction="entry", minutes=0, track_id=1))
    exit_res = ingest_event(db, make_event(direction="exit", minutes=125, track_id=2))
    db.commit()

    s = db.get(Session, exit_res.session_id)
    assert s.entry_event_id is not None and s.exit_event_id is not None
    assert s.duration_seconds == 125 * 60
    assert s.is_current is False


def test_second_entry_marks_previous_session_missing_exit(db):
    seed_vehicle(db, "34ABC123")
    r1 = ingest_event(db, make_event(direction="entry", minutes=0, track_id=1))
    r2 = ingest_event(db, make_event(direction="entry", minutes=600, track_id=2))
    db.commit()

    prev = db.get(Session, r1.session_id)
    curr = db.get(Session, r2.session_id)
    assert prev.missing_exit is True
    assert curr.is_current is True
    # "su an iceride" = 1 arac (curr), stale olan sayilmaz
    current = db.scalars(
        select(Session).where(Session.exit_event_id.is_(None), Session.missing_exit.is_(False))
    ).all()
    assert len(current) == 1 and current[0].id == curr.id


def test_exit_without_entry_creates_missing_entry_session(db):
    seed_vehicle(db, "34ABC123")
    res = ingest_event(db, make_event(direction="exit", minutes=30))
    db.commit()

    s = db.get(Session, res.session_id)
    assert s.missing_entry is True
    assert s.entry_event_id is None
    assert s.exit_event_id is not None


def test_unmatched_plate_still_forms_session_by_plate(db):
    # Hic kayitli arac yok - plaka bazli eslesme
    ingest_event(db, make_event(plate="55XYZ42", direction="entry", minutes=0))
    exit_res = ingest_event(db, make_event(plate="55 XYZ 42", direction="exit", minutes=60))
    db.commit()

    s = db.get(Session, exit_res.session_id)
    assert s.vehicle_id is None
    assert s.canonical_plate == "55XYZ42"
    assert s.exit_event_id is not None


def test_out_of_order_exit_then_entry_reconciles_to_one_session(db):
    # S8 "sirasiz gelisler": cikis, girisinden ONCE teslim edilir.
    seed_vehicle(db, "34ABC123")
    exit_res = ingest_event(db, make_event(direction="exit", minutes=180, track_id=2))
    db.commit()
    s_after_exit = db.get(Session, exit_res.session_id)
    assert s_after_exit.missing_entry is True

    entry_res = ingest_event(db, make_event(direction="entry", minutes=0, track_id=1))
    db.commit()

    # Ayni session geriye dolduruldu - yeni session ACILMADI.
    assert entry_res.session_id == exit_res.session_id
    assert db.scalar(select(func.count()).select_from(Session)) == 1
    s = db.get(Session, exit_res.session_id)
    assert s.entry_event_id is not None and s.exit_event_id is not None
    assert s.missing_entry is False
    assert s.duration_seconds == 180 * 60


def test_out_of_order_by_plate_when_vehicle_unknown(db):
    exit_res = ingest_event(db, make_event(plate="80KRV73", direction="exit", minutes=90))
    entry_res = ingest_event(db, make_event(plate="80 KRV 73", direction="entry", minutes=0))
    db.commit()
    assert entry_res.session_id == exit_res.session_id
    assert db.scalar(select(func.count()).select_from(Session)) == 1
    s = db.get(Session, exit_res.session_id)
    assert s.missing_entry is False and s.duration_seconds == 90 * 60


def test_stale_orphan_exit_beyond_merge_window_not_backfilled(db):
    seed_vehicle(db, "34ABC123")
    # cikis, giristen 30 gun sonra (MERGE_WINDOW = 14 gun)
    ingest_event(db, make_event(direction="exit", minutes=30 * 24 * 60))
    ingest_event(db, make_event(direction="entry", minutes=0))
    db.commit()
    # Backfill YAPILMAZ - iki ayri session kalir.
    assert db.scalar(select(func.count()).select_from(Session)) == 2
