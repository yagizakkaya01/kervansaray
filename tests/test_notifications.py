from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from kervansaray.db.models import (
    Direction,
    Event,
    MatchStatus,
    Person,
    PersonKind,
    Session,
    Vehicle,
)
from kervansaray.notifications import Notification, NotificationBroker, evaluate_event


def test_broker_publish_and_subscribe():
    b = NotificationBroker(history_limit=3)
    q = b.subscribe()

    n1 = Notification(
        "1", "blacklist", "critical", "34VIP99", "Alarm", "Kara liste", "2026-04-15T12:00:00Z"
    )
    n2 = Notification(
        "2", "unregistered", "warning", "06XYZ01", "Uyarı", "Kayıtsız", "2026-04-15T12:01:00Z"
    )
    n3 = Notification(
        "3", "guest_arrival", "info", "34GUEST1", "Bilgi", "Misafir", "2026-04-15T12:02:00Z"
    )
    n4 = Notification(
        "4", "overstay", "warning", "34LONG1", "Uyarı", "Süre aşımı", "2026-04-15T12:03:00Z"
    )

    b.publish(n1)
    b.publish(n2)
    b.publish(n3)
    b.publish(n4)

    # Abone tüm bildirimleri sırayla almalı
    assert q.get_nowait().id == "1"
    assert q.get_nowait().id == "2"
    assert q.get_nowait().id == "3"
    assert q.get_nowait().id == "4"

    # Halka bellek en fazla 3 tutmalı (en yeni 3)
    recent = b.get_recent()
    assert len(recent) == 3
    assert recent[0]["id"] == "4"
    assert recent[1]["id"] == "3"
    assert recent[2]["id"] == "2"

    b.unsubscribe(q)


def test_broker_max_subscribers_ceiling():
    b = NotificationBroker(max_subscribers=2)
    q1 = b.subscribe()
    q2 = b.subscribe()
    assert q1 is not None
    assert q2 is not None

    # Limit aşıldığında None dönmeli
    q3 = b.subscribe()
    assert q3 is None

    # Biri ayrıldığında tekrar yer açılmalı
    b.unsubscribe(q1)
    q4 = b.subscribe()
    assert q4 is not None



def test_evaluate_event_blacklist():
    db = MagicMock()
    v = Vehicle(id=10, plate="34VIP99", is_blacklisted=True)
    ev = Event(
        event_id="ev-1",
        raw_plate="34 VIP 99",
        canonical_plate="34VIP99",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=10,
        vehicle=v,
        ts=datetime(2026, 4, 15, 14, 0, tzinfo=UTC),
    )

    notifs = evaluate_event(db, ev)
    rules = [n.rule for n in notifs]
    assert "blacklist" in rules
    bl_notif = next(n for n in notifs if n.rule == "blacklist")
    assert bl_notif.severity == "critical"
    assert "KARA LİSTE" in bl_notif.title
    assert "34VIP99" in bl_notif.plate


def test_evaluate_event_unregistered_entry():
    db = MagicMock()
    ev = Event(
        event_id="ev-2",
        raw_plate="14 EV 669",
        canonical_plate="14EV669",
        direction=Direction.entry,
        match_status=MatchStatus.unmatched,
        camera_id="cam-01",
        vehicle_id=None,
        vehicle=None,
        ts=datetime(2026, 4, 15, 15, 0, tzinfo=UTC),
    )

    notifs = evaluate_event(db, ev)
    rules = [n.rule for n in notifs]
    assert "unregistered" in rules
    unreg = next(n for n in notifs if n.rule == "unregistered")
    assert unreg.severity == "warning"
    assert "Kayıtsız Araç" in unreg.title


def test_evaluate_event_pending_review():
    db = MagicMock()
    ev = Event(
        event_id="ev-3",
        raw_plate="34 ABC 12",
        canonical_plate="34ABC123",
        direction=Direction.entry,
        match_status=MatchStatus.pending,
        candidate_vehicle_id=42,
        camera_id="cam-01",
        vehicle_id=None,
        vehicle=None,
        ts=datetime(2026, 4, 15, 16, 0, tzinfo=UTC),
    )

    notifs = evaluate_event(db, ev)
    rules = [n.rule for n in notifs]
    assert "pending_review" in rules
    pending = next(n for n in notifs if n.rule == "pending_review")
    assert pending.severity == "warning"
    assert "Onayı Bekliyor" in pending.title


def test_evaluate_event_guest_arrival():
    db = MagicMock()
    p = Person(id=1, name="Ahmet Yılmaz", kind=PersonKind.guest, room_no="304")
    v = Vehicle(id=5, plate="34GUEST1", person=p, is_blacklisted=False)
    ev = Event(
        event_id="ev-4",
        raw_plate="34 GUEST 1",
        canonical_plate="34GUEST1",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=5,
        vehicle=v,
        ts=datetime(2026, 4, 15, 17, 0, tzinfo=UTC),
    )

    notifs = evaluate_event(db, ev)
    rules = [n.rule for n in notifs]
    assert "guest_arrival" in rules
    ga = next(n for n in notifs if n.rule == "guest_arrival")
    assert ga.severity == "info"
    assert "Ahmet Yılmaz" in ga.title
    assert "Oda: 304" in ga.message


def test_evaluate_event_overstay():
    db = MagicMock()
    # 52 saatlik park süresi
    mock_session = Session(
        id=99,
        canonical_plate="06STAY99",
        duration_seconds=52 * 3600,
    )
    db.scalar.return_value = mock_session

    ev = Event(
        id=200,
        event_id="ev-exit",
        raw_plate="06 STAY 99",
        canonical_plate="06STAY99",
        direction=Direction.exit,
        match_status=MatchStatus.exact,
        camera_id="cam-exit-1",
        vehicle_id=8,
        vehicle=None,
        ts=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
    )

    notifs = evaluate_event(db, ev)
    rules = [n.rule for n in notifs]
    assert "overstay" in rules
    ov = next(n for n in notifs if n.rule == "overstay")
    assert ov.severity == "warning"
    assert "52.0 saat" in ov.message


def test_evaluate_event_night_entry():
    db = MagicMock()
    tr_tz = timezone(timedelta(hours=3))

    # 1. TR saati 03:28 (gerçek gece girişi) -> alarm tetiklenmeli
    ev_tr_night = Event(
        event_id="ev-night-1",
        raw_plate="38 HE 907",
        canonical_plate="38HE907",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=7,
        vehicle=Vehicle(id=7, plate="38HE907", is_blacklisted=False),
        ts=datetime(2026, 4, 15, 3, 28, tzinfo=tr_tz),
    )
    notifs1 = evaluate_event(db, ev_tr_night)
    rules1 = [n.rule for n in notifs1]
    assert "night_entry" in rules1
    ne1 = next(n for n in notifs1 if n.rule == "night_entry")
    assert ne1.severity == "info"
    assert "Gece Girişi" in ne1.title
    assert ne1.metadata["hour"] == 3

    # 2. TR saati 22:00 (normal akşam girişi) -> gece alarmı OLMAMALI (3 saat kayma hatası önleme)
    ev_tr_evening = Event(
        event_id="ev-night-2",
        raw_plate="38 HE 907",
        canonical_plate="38HE907",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=7,
        vehicle=Vehicle(id=7, plate="38HE907", is_blacklisted=False),
        ts=datetime(2026, 4, 15, 22, 0, tzinfo=tr_tz),
    )
    notifs2 = evaluate_event(db, ev_tr_evening)
    assert "night_entry" not in [n.rule for n in notifs2]

    # 3. UTC 00:30 -> TR saati 03:30 (gece) -> alarm tetiklenmeli
    ev_utc = Event(
        event_id="ev-night-3",
        raw_plate="38 HE 907",
        canonical_plate="38HE907",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=7,
        vehicle=Vehicle(id=7, plate="38HE907", is_blacklisted=False),
        ts=datetime(2026, 4, 15, 0, 30, tzinfo=UTC),
    )
    notifs3 = evaluate_event(db, ev_utc)
    assert "night_entry" in [n.rule for n in notifs3]


def test_routes_notifications():
    from kervansaray.api import create_app
    from kervansaray.notifications import broker

    broker.clear()
    broker.publish(
        Notification(
            "t1", "blacklist", "critical", "34TEST1", "Test Alarm", "Mesaj", "2026-04-15T12:00:00Z"
        )
    )

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    # GET /api/notifications
    r = c.get("/api/notifications")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 1
    assert data["notifications"][0]["plate"] == "34TEST1"

    # GET /api/notifications/stream head / type check
    r_stream = c.get("/api/notifications/stream", buffered=False)
    assert r_stream.status_code == 200
    assert "text/event-stream" in r_stream.content_type

    # Abone tavani asildiginda 503 Service Unavailable donmeli (thread starvation onleme)
    with patch.object(broker, "subscribe", return_value=None):
        r_full = c.get("/api/notifications/stream")
        assert r_full.status_code == 503
        assert "limitine ulasildi" in r_full.get_json()["error"]



def test_routes_events_post_commit_and_notify_bypass():
    from kervansaray.api import create_app
    from kervansaray.ingest import IngestResult
    from kervansaray.notifications import broker

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    payload = {
        "schema_version": "1.0",
        "event_id": "00000000-0000-0000-0000-000000000099",
        "device_id": "dev-01",
        "camera_id": "cam-01",
        "ts": "2026-04-15T03:28:00+03:00",
        "plate": "34VIP99",
        "plate_confidence": 0.95,
        "direction": "entry",
        "track_id": 1,
        "crop_ref": None,
        "model_version": "v1",
    }

    mock_ev = Event(
        id=99,
        event_id=payload["event_id"],
        raw_plate="34VIP99",
        canonical_plate="34VIP99",
        direction=Direction.entry,
        match_status=MatchStatus.exact,
        camera_id="cam-01",
        vehicle_id=1,
        vehicle=Vehicle(id=1, plate="34VIP99", is_blacklisted=True),
        ts=datetime(2026, 4, 15, 3, 28, tzinfo=timezone(timedelta(hours=3))),
    )

    fake_result = IngestResult(
        event_row_id=99,
        event_id=payload["event_id"],
        duplicate=False,
        match_status=MatchStatus.exact,
        vehicle_id=1,
        session_id=10,
        session_closed=False,
    )

    mock_db = MagicMock()
    mock_db.get.return_value = mock_ev

    @contextmanager
    def successful_scope():
        yield mock_db

    # 1. Normal POST -> commit basarili -> bildirim broker'a gitmeli
    broker.clear()
    with patch("kervansaray.api.routes_events.session_scope", successful_scope), \
         patch("kervansaray.api.routes_events.ingest_event", return_value=fake_result):
        r1 = c.post("/events", json=payload)
        assert r1.status_code == 201
        recent = broker.get_recent()
        assert len(recent) >= 1
        assert any(n["rule"] == "blacklist" for n in recent)

    # 2. ?notify=false ile POST -> bildirim yayinlanmamali (bulk ingest optimizasyonu)
    broker.clear()
    with patch("kervansaray.api.routes_events.session_scope", successful_scope), \
         patch("kervansaray.api.routes_events.ingest_event", return_value=fake_result):
        r2 = c.post("/events?notify=false", json=payload)
        assert r2.status_code == 201
        assert len(broker.get_recent()) == 0

    # 3. Commit sirasinda DB patlarsa -> phantom bildirim GİTMEMELİ
    broker.clear()

    @contextmanager
    def failing_scope():
        yield mock_db
        raise RuntimeError("DB connection dropped during commit!")

    with patch("kervansaray.api.routes_events.session_scope", failing_scope), \
         patch("kervansaray.api.routes_events.ingest_event", return_value=fake_result):
        try:
            c.post("/events", json=payload)
        except RuntimeError:
            pass
        assert len(broker.get_recent()) == 0

