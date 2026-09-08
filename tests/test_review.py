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

    mock_db = MagicMock()
    mock_db.scalar.return_value = ev

    mock_reconcile = MagicMock()
    monkeypatch.setattr("kervansaray.ingest.sessions.reconcile_vehicle_sessions", mock_reconcile)

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
    # Session mutabakatı tetiklenmiş olmalı
    mock_reconcile.assert_called_once_with(mock_db, 20, {"06XYZO1", "06XYZ01"})


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

    mock_reconcile = MagicMock()
    monkeypatch.setattr("kervansaray.ingest.sessions.reconcile_vehicle_sessions", mock_reconcile)

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
    # Reconcile tetiklenmiş olmalı
    mock_reconcile.assert_called_once_with(mock_db, None, {"34UNK99"})


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


def test_review_bad_limit_returns_400():
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    # ?limit=abc -> 400 (500 degil)
    r1 = c.get("/api/review?limit=abc")
    assert r1.status_code == 400
    assert "gecersiz limit" in r1.get_json()["error"]

    # ?limit=-10 -> 400
    r2 = c.get("/api/review?limit=-10")
    assert r2.status_code == 400


def test_public_mode_disables_operator_routes(monkeypatch):
    from kervansaray.config import settings

    monkeypatch.setattr(settings, "ENABLE_OPERATOR_ROUTES", False)
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    # 1. /api/review uclari hic kaydedilmemeli (404)
    r_review = c.get("/api/review")
    assert r_review.status_code == 404

    # 2. POST /events yazma yolu 403 donmeli (mutasyon engelleme)
    r_post_events = c.post("/events", json={"test": 1})
    assert r_post_events.status_code == 403
    assert "Public demo modunda" in r_post_events.get_json()["error"]


def test_reconcile_vehicle_sessions_merges_orphan_exit():
    from kervansaray.ingest.sessions import reconcile_vehicle_sessions

    # Senaryo: 10:00'da bozuk plaka 34ABD123 ile giris (pending)
    #          12:00'da dogru plaka 34ABC123 ile cikis (orphan exit)
    ev_entry = Event(
        id=101,
        event_id="ev-entry-1",
        raw_plate="34 ABD 123",
        canonical_plate="34ABC123",  # Onay sonrasi kanoniklesmis
        direction=Direction.entry,
        vehicle_id=55,
        match_status=MatchStatus.fuzzy,
        ts=datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
    )
    ev_exit = Event(
        id=102,
        event_id="ev-exit-1",
        raw_plate="34 ABC 123",
        canonical_plate="34ABC123",
        direction=Direction.exit,
        vehicle_id=55,
        match_status=MatchStatus.exact,
        ts=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
    )

    old_entry_session = Session(
        id=1,
        entry_event_id=101,
        entry_ts=ev_entry.ts,
        canonical_plate="34ABD123",
        vehicle_id=None,
        missing_exit=False,
    )
    old_exit_session = Session(
        id=2,
        exit_event_id=102,
        exit_ts=ev_exit.ts,
        canonical_plate="34ABC123",
        vehicle_id=55,
        missing_entry=True,
    )

    # Mock DB:
    # 1. Eski sessionlari listeler -> [old_entry_session, old_exit_session]
    # 2. Olaylari kronolojik listeler -> [ev_entry, ev_exit]
    mock_db = MagicMock()
    mock_db.scalars.side_effect = [
        [old_entry_session, old_exit_session],  # silinecek session'lar
        [ev_entry, ev_exit],                    # sirayla replay edilecek event'ler
        None,                                   # _find_orphan_exit (ev_entry)
        None,                                   # _find_current_session (ev_entry)
    ]

    # Reconcile calistir
    reconciled = reconcile_vehicle_sessions(mock_db, vehicle_id=55, plates={"34ABD123", "34ABC123"})

    # Eski 2 session silinmis olmali
    assert mock_db.delete.call_count == 2
    mock_db.delete.assert_any_call(old_entry_session)
    mock_db.delete.assert_any_call(old_exit_session)

    # 2 event replay edildi
    assert len(reconciled) == 2

