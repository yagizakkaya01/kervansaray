"""Plaka mutabakati testleri (PROJECT_BRIEF S3.8)."""
from kervansaray.db.models import MatchStatus
from kervansaray.ingest import reconcile_plate
from tests._helpers import seed_vehicle


def test_exact_match(db):
    v = seed_vehicle(db, "34ABC123")
    r = reconcile_plate(db, "34 abc 123")
    assert r.status == MatchStatus.exact
    assert r.vehicle_id == v.id
    assert r.canonical_plate == "34ABC123"


def test_unmatched_when_no_vehicle(db):
    seed_vehicle(db, "34ABC123")
    r = reconcile_plate(db, "06XYZ999")
    assert r.status == MatchStatus.unmatched
    assert r.vehicle_id is None
    assert r.candidate_vehicle_id is None


def test_edit_distance_one_is_pending_not_auto_accepted(db):
    v = seed_vehicle(db, "34ABC123")
    r = reconcile_plate(db, "34ABC124")  # tek karakter fark
    assert r.status == MatchStatus.pending
    assert r.vehicle_id is None  # otomatik kabul YOK
    assert r.candidate_vehicle_id == v.id
    assert r.score is not None and r.score < 100


def test_far_plate_not_even_a_candidate(db):
    seed_vehicle(db, "34ABC123")
    r = reconcile_plate(db, "34ZZZ999")
    assert r.status == MatchStatus.unmatched
