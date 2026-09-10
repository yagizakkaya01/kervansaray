"""query_events / aggregate_events yeni parametreleri: person, person_kind, plate.

Referans: docs/TOOL_PARAMETER_EXPANSION_REVIEW.md (G1-G3 + C1).
"""
from datetime import timedelta

from kervansaray.db.models import PersonKind
from kervansaray.ingest import ingest_event
from kervansaray.query_pipeline import format_narrative
from kervansaray.tools import aggregate_events, query_events
from tests._helpers import BASE_TS, make_event, seed_vehicle

_START = BASE_TS - timedelta(days=1)
_END = BASE_TS + timedelta(days=1)


def _ingest(db, **kw):
    return ingest_event(db, make_event(**kw))


def _setup(db):
    # Personel — unvanlı, aksanlı
    seed_vehicle(db, "26ABC2626", person_name="Tarık Akkaya",
                 kind=PersonKind.staff, title="Güvenlik Müdürü",
                 label="Guvenlik Muduru - Nizamiye")
    # Misafir
    seed_vehicle(db, "06AK0052", person_name="Can Ozturk", kind=PersonKind.guest)
    # Tedarikçi
    seed_vehicle(db, "10NS5918", person_name="Ege Gida", kind=PersonKind.vendor)
    # Kayıtsız (person yok)
    seed_vehicle(db, "26XYZ413")

    _ingest(db, plate="26ABC2626", direction="entry", minutes=0, track_id=1)
    _ingest(db, plate="26ABC2626", direction="exit", minutes=60, track_id=2)
    _ingest(db, plate="26ABC2626", direction="entry", minutes=120, track_id=3)
    _ingest(db, plate="06AK0052", direction="entry", minutes=10, track_id=4)
    _ingest(db, plate="10NS5918", direction="entry", minutes=20, track_id=5)
    _ingest(db, plate="26XYZ413", direction="entry", minutes=30, track_id=6)
    db.commit()


def test_person_filter_matches_title_accent_insensitive(db):
    _setup(db)
    # sorgu terimi küçük harf + tam aksanlı; kayıt "Güvenlik Müdürü"
    r = query_events(db, start=_START, end=_END, person="güvenlik müdürü")
    plates = {row["plaka"] for row in r.rows}
    assert plates == {"26ABC2626"}
    assert all(row["unvan"] == "Güvenlik Müdürü" for row in r.rows)


def test_person_filter_matches_ascii_term(db):
    _setup(db)
    # aksansız arama da eşleşmeli ("mudur" -> "Müdür")
    r = query_events(db, start=_START, end=_END, person="mudur")
    assert {row["plaka"] for row in r.rows} == {"26ABC2626"}


def test_person_filter_matches_name(db):
    _setup(db)
    r = query_events(db, start=_START, end=_END, person="tarık akkaya")
    assert {row["plaka"] for row in r.rows} == {"26ABC2626"}


def test_person_filter_no_match_is_empty_not_all(db):
    _setup(db)
    r = query_events(db, start=_START, end=_END, person="genel müdür")
    assert r.rows == []
    # narrative 0-satırı net söylemeli, "13 kayıt bulundu" dememeli
    n = format_narrative("query_events", {"person": "genel müdür"}, r)
    assert "genel müdür" in n and "bulunamadı" in n


def test_person_kind_staff_filter(db):
    _setup(db)
    r = query_events(db, start=_START, end=_END, person_kind="staff")
    assert {row["plaka"] for row in r.rows} == {"26ABC2626"}


def test_person_kind_unknown_is_null(db):
    _setup(db)
    r = query_events(db, start=_START, end=_END, person_kind="unknown")
    assert {row["plaka"] for row in r.rows} == {"26XYZ413"}
    assert all(row["kisi"] is None for row in r.rows)


def test_aggregate_plate_filter(db):
    _setup(db)
    r = aggregate_events(db, metric="count", start=_START, end=_END, plate="26 abc 2626")
    assert r.scalar == 3  # canonicalize + 3 olay


def test_aggregate_person_kind_filter(db):
    _setup(db)
    r = aggregate_events(db, metric="count", start=_START, end=_END,
                         person_kind="vendor", direction="entry")
    assert r.scalar == 1


def test_aggregate_person_kind_invalid_raises(db):
    _setup(db)
    try:
        aggregate_events(db, metric="count", start=_START, end=_END, person_kind="patron")
    except ValueError:
        return
    raise AssertionError("geçersiz person_kind ValueError vermeli")
