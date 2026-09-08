"""Plaka onay kuyruğu (Review Queue) testleri (ROADMAP Faz 8)."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from kervansaray.api import create_app
from kervansaray.db.models import (
    Direction,
    Event,
    MatchStatus,
    Person,
    PersonKind,
    Session,
    Vehicle,
)


def test_list_pending_reviews(monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    p = Person(id=1, name="Ahmet Yılmaz", kind=PersonKind.guest)
    v = Vehicle(id=10, plate="34VIP99", person=p, is_blacklisted=False)
    ev = Event(
        id=1,
        event_id="00000000-0000-0000-0000-000000000001",
        raw_plate="34 V1P 99",
        canonical_plate="34V1P99",
        direction=Direction.entry,
        match_status=MatchStatus.pending,
        match_score=94.0,
        candidate_vehicle_id=10,
        candidate_vehicle=v,
        camera_id="cam-01",
        ts=datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
    )

    mock_db = MagicMock()
    mock_db.scalars.return_value = [ev]

    from contextlib import contextmanager

    @contextmanager
    def fake_scope():
        yield mock_db

    monkeypatch.setattr("kervansaray.api.routes_review.session_scope", fake_scope)

    r = c.get("/api/review")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 1
    item = data["pending"][0]
    assert item["event_id"] == ev.event_id
    assert item["raw_plate"] == "34 V1P 99"
    assert item["candidate_plate"] == "34VIP99"
    assert item["candidate_owner"] == "Ahmet Yılmaz"
    assert item["candidate_kind"] == "guest"
    assert item["match_score"] == 94.0


def test_approve_candidate_success(monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    p = Person(id=1, name="Mehmet Demir", kind=PersonKind.staff)
    v = Vehicle(id=20, plate="06XYZ01", person=p, is_blacklisted=False)
    ev = Event(
        id=2,
        event_id="00000000-0000-0000-0000-000000000002",
        raw_plate="06 XYZ O1",
        canonical_plate="06XYZO1",
        direction=Direction.entry,
        match_status=MatchStatus.pending,
        match_score=88.0,
        candidate_vehicle_id=20,
        candidate_vehicle=v,
        vehicle_id=None,
        camera_id="cam-02",
        ts=datetime(2026, 4, 15, 11, 0, tzinfo=UTC),
    )
    sess = Session(
        id=5,
        entry_event_id=ev.id,
        canonical_plate=ev.canonical_plate,
        vehicle_id=None,
        missing_entry=False,
        missing_exit=False,
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = ev
    mock_db.scalars.return_value = [sess]

    from contextlib import contextmanager

    @contextmanager
    def fake_scope():
        yield mock_db

    monkeypatch.setattr("kervansaray.api.routes_review.session_scope", fake_scope)

    r = c.post(f"/api/review/{ev.event_id}/approve")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["status"] == "fuzzy"
    assert data["plate"] == "06XYZ01"
    assert data["vehicle_id"] == 20

    # Model alanları güncellenmiş olmalı
    assert ev.match_status == MatchStatus.fuzzy
    assert ev.vehicle_id == 20
    assert ev.canonical_plate == "06XYZ01"
    # İlişkili Session güncellenmiş olmalı
    assert sess.vehicle_id == 20
    assert sess.canonical_plate == "06XYZ01"


def test_reject_candidate_success(monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    ev = Event(
        id=3,
        event_id="00000000-0000-0000-0000-000000000003",
        raw_plate="34 UNK 99",
        canonical_plate="34UNK99",
        direction=Direction.entry,
        match_status=MatchStatus.pending,
        match_score=86.0,
        candidate_vehicle_id=30,
        vehicle_id=None,
        camera_id="cam-01",
        ts=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = ev

    from contextlib import contextmanager

    @contextmanager
    def fake_scope():
        yield mock_db

    monkeypatch.setattr("kervansaray.api.routes_review.session_scope", fake_scope)

    r = c.post(f"/api/review/{ev.event_id}/reject")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["status"] == "unmatched"

    assert ev.match_status == MatchStatus.unmatched
    assert ev.candidate_vehicle_id is None


def test_review_not_found_and_not_pending(monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    mock_db = MagicMock()
    from contextlib import contextmanager

    @contextmanager
    def fake_scope():
        yield mock_db

    monkeypatch.setattr("kervansaray.api.routes_review.session_scope", fake_scope)

    # 1. Bulunamayan event_id -> 404
    mock_db.scalar.return_value = None
    r1 = c.post("/api/review/non-existent-id/approve")
    assert r1.status_code == 404

    # 2. Zaten exact/onaylanmış event_id -> 400
    ev_already_exact = Event(
        id=4,
        event_id="ev-exact",
        match_status=MatchStatus.exact,
    )
    mock_db.scalar.return_value = ev_already_exact
    r2 = c.post("/api/review/ev-exact/approve")
    assert r2.status_code == 400
