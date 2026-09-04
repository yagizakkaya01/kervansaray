"""Faz 2 cikis kriteri: aylarca sentetik olay uretilip yuklenebiliyor,
ground-truth manifest ile dogrulanabiliyor (PROJECT_BRIEF S8).
"""
from datetime import date

import pytest
from sqlalchemy import func, select

from kervansaray.db.models import Direction, Event, MatchStatus, Session, Vehicle
from kervansaray.synth import TR, generate
from tests._helpers import load_scenario

SEED = 424242


@pytest.fixture(scope="module")
def scenario():
    # Kucuk ama tam: tum anomaliler + tum kir turleri.
    return generate(seed=SEED, start=date(2026, 4, 1), days=45, size=120)


@pytest.fixture
def loaded(db, scenario):
    load_scenario(db, scenario)
    return scenario


def test_duplicates_are_deduped(loaded, db):
    # Teslim edilen akista tekrarlar var; DB'de her event_id bir kez.
    stored = db.scalar(select(func.count()).select_from(Event))
    assert stored == loaded.manifest["counts"]["events_unique"]
    assert loaded.manifest["counts"]["events_delivered"] > stored


def test_no_duplicate_sessions_from_out_of_order(loaded, db):
    # Sirasi bozuk teslimler ayni ziyaret icin iki session yaratmamali.
    # Ustten sinir: session sayisi teslim edilen "ziyaret" sayisini asmamali.
    sessions = db.scalar(select(func.count()).select_from(Session))
    entries = db.scalar(
        select(func.count()).select_from(Event).where(Event.direction == Direction.entry)
    )
    exits = db.scalar(
        select(func.count()).select_from(Event).where(Event.direction == Direction.exit)
    )
    # Her session en az bir olaydan dogar; ideal durumda ~ max(entries, exits).
    assert sessions <= entries + exits
    assert sessions >= max(entries, exits) * 0.5


def test_blacklisted_vehicle_resolves_exact(loaded, db):
    plate = loaded.manifest["anomalies"]["blacklisted"]["plate"]
    v = db.scalar(select(Vehicle).where(Vehicle.plate == plate))
    assert v is not None and v.is_blacklisted is True
    evs = db.scalars(select(Event).where(Event.vehicle_id == v.id)).all()
    assert evs and all(e.match_status == MatchStatus.exact for e in evs)


def test_three_day_stay_has_long_session(loaded, db):
    plate = loaded.manifest["anomalies"]["three_day_stay"]["plate"]
    v = db.scalar(select(Vehicle).where(Vehicle.plate == plate))
    s = db.scalar(
        select(Session).where(Session.vehicle_id == v.id, Session.duration_seconds.isnot(None))
    )
    assert s is not None
    days = s.duration_seconds / 86400
    assert 2.7 < days < 3.3


def test_recurring_unregistered_five_unmatched_entries(loaded, db):
    plate = loaded.manifest["anomalies"]["recurring_unregistered"]["plate"]
    entries = db.scalars(
        select(Event).where(
            Event.canonical_plate == plate, Event.direction == Direction.entry
        )
    ).all()
    assert len(entries) == 5
    assert all(e.match_status == MatchStatus.unmatched for e in entries)
    assert all(e.vehicle_id is None for e in entries)


def test_night_entry_present(loaded, db):
    plate = loaded.manifest["anomalies"]["night_entry"]["plate"]
    e = db.scalar(
        select(Event).where(
            Event.canonical_plate == plate, Event.direction == Direction.entry
        )
    )
    assert e is not None
    assert e.ts.astimezone(TR).hour == 3


def test_synthetic_province_events_are_unmatched(loaded, db):
    for plate in loaded.manifest["synthetic_plates"]:
        evs = db.scalars(select(Event).where(Event.canonical_plate == plate)).all()
        assert evs  # akista gorunuyorlar
        # 82-99 il kodlu araclar DB'ye yazilmaz -> hicbir eslesme.
        assert all(e.match_status == MatchStatus.unmatched for e in evs)
        assert all(e.vehicle_id is None for e in evs)


def test_cars_currently_inside_is_bounded(loaded, db):
    inside = db.scalars(
        select(Session).where(
            Session.exit_event_id.is_(None), Session.missing_exit.is_(False)
        )
    ).all()
    # Negatif olamaz, populasyondan buyuk olamaz.
    assert 0 <= len(inside) <= loaded.manifest["population_size"]
