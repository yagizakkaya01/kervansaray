"""Tool katmani birim testleri (PROJECT_BRIEF S3.2 - "each tool is
unit-testable in isolation")."""
from datetime import timedelta

from kervansaray.ingest import ingest_event
from kervansaray.tools import (
    MAX_ROWS,
    aggregate_events,
    find_anomalies,
    occupancy,
    query_events,
    vehicle_history,
)
from tests._helpers import BASE_TS, make_event, seed_vehicle

_START = BASE_TS - timedelta(days=1)
_END = BASE_TS + timedelta(days=1)


def _ingest(db, **kw):
    return ingest_event(db, make_event(**kw))


def test_aggregate_count_and_direction_filter(db):
    seed_vehicle(db, "34ABC123")
    _ingest(db, direction="entry", minutes=0, track_id=1)
    _ingest(db, direction="exit", minutes=60, track_id=2)
    _ingest(db, plate="06XYZ99", direction="entry", minutes=30, track_id=3)
    db.commit()

    assert aggregate_events(db, metric="count", start=_START, end=_END).scalar == 3
    r = aggregate_events(db, metric="count", start=_START, end=_END, direction="entry")
    assert r.scalar == 2
    u = aggregate_events(db, metric="unique_plates", start=_START, end=_END)
    assert u.scalar == 2


def test_aggregate_group_by_direction(db):
    seed_vehicle(db, "34ABC123")
    _ingest(db, direction="entry", minutes=0, track_id=1)
    _ingest(db, direction="entry", minutes=10, track_id=2)
    _ingest(db, direction="exit", minutes=60, track_id=3)
    db.commit()
    rows = aggregate_events(
        db, metric="count", start=_START, end=_END, group_by="direction"
    ).rows
    got = {r["group"]: r["value"] for r in rows}
    assert got == {"entry": 2, "exit": 1}


def test_query_events_caps_at_max_rows(db):
    seed_vehicle(db, "34ABC123")
    for i in range(MAX_ROWS + 5):
        _ingest(db, direction="entry", minutes=i, track_id=i + 1)
    db.commit()
    r = query_events(db, start=_START, end=_END)
    assert len(r.rows) == MAX_ROWS
    assert r.truncated is True
    assert r.note is not None


def test_query_events_plate_filter_canonicalises(db):
    seed_vehicle(db, "34ABC123")
    _ingest(db, plate="34ABC123", direction="entry", minutes=0, track_id=1)
    _ingest(db, plate="06XYZ99", direction="entry", minutes=5, track_id=2)
    db.commit()
    r = query_events(db, start=_START, end=_END, plate="34 abc 123")
    assert len(r.rows) == 1
    assert r.rows[0]["plate"] == "34ABC123"
    assert r.event_ids == [r.rows[0]["event_id"]]


def test_vehicle_history_known_vs_unknown(db):
    seed_vehicle(db, "34ABC123", person_name="Ada", blacklisted=True)
    _ingest(db, plate="34ABC123", direction="entry", minutes=0, track_id=1)
    _ingest(db, plate="99ZZ88", direction="entry", minutes=5, track_id=2)
    db.commit()

    known = vehicle_history(db, plate="34 ABC 123")
    assert known.scalar["known"] is True
    assert known.scalar["is_blacklisted"] is True
    assert known.scalar["event_count"] == 1

    unknown = vehicle_history(db, plate="99ZZ88")
    assert unknown.scalar["known"] is False
    assert unknown.scalar["event_count"] == 1


def test_occupancy_counts_open_sessions(db):
    seed_vehicle(db, "34ABC123")
    seed_vehicle(db, "06XYZ99")
    _ingest(db, plate="34ABC123", direction="entry", minutes=0, track_id=1)
    _ingest(db, plate="06XYZ99", direction="entry", minutes=10, track_id=2)
    _ingest(db, plate="34ABC123", direction="exit", minutes=90, track_id=3)
    db.commit()
    r = occupancy(db)
    assert r.scalar == 1
    assert r.rows[0]["plate"] == "06XYZ99"


def test_find_anomalies_blacklist_and_night(db):
    seed_vehicle(db, "34ABC123", blacklisted=True)
    _ingest(db, plate="34ABC123", direction="entry", minutes=0, track_id=1)
    # gece 03:00 girisi
    night_ts = BASE_TS.replace(hour=3, minute=15)
    ingest_event(db, make_event(plate="55GECE12", direction="entry", ts=night_ts, track_id=9))
    db.commit()

    blk = find_anomalies(db, rule="blacklist", start=_START, end=_END)
    assert [r["plate"] for r in blk.rows] == ["34ABC123"]

    night = find_anomalies(db, rule="night_entry", start=_START, end=_END)
    assert "55GECE12" in {r["plate"] for r in night.rows}


def test_find_anomalies_rejects_unknown_rule(db):
    import pytest

    with pytest.raises(ValueError, match="rule"):
        find_anomalies(db, rule="teleport", start=_START, end=_END)
