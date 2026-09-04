"""Sentetik uretici - saf/deterministik testler (DB gerekmez)."""
from datetime import date

import pytest

from kervansaray.events import EventV1
from kervansaray.synth import TR, DirtConfig, generate
from kervansaray.text.plates import parse

SEED = 20260904


@pytest.fixture(scope="module")
def scenario():
    return generate(seed=SEED, start=date(2026, 3, 1), days=60, size=150)


def test_deterministic(scenario):
    again = generate(seed=SEED, start=date(2026, 3, 1), days=60, size=150)
    assert [g.payload.model_dump_json() for g in scenario.stream] == [
        g.payload.model_dump_json() for g in again.stream
    ]


def test_all_payloads_are_valid_eventv1(scenario):
    for g in scenario.stream:
        assert isinstance(g.payload, EventV1)
        assert g.payload.ts.tzinfo is not None


def test_plate_convention(scenario):
    # Kutle: gercek il kodu (01-81) ve gecerli dilbilgisi.
    bulk = [v for v in scenario.population.vehicles if not v.synthetic]
    for v in bulk:
        p = parse(v.plate)
        assert p.valid, (v.plate, p.reason)
        assert 1 <= p.province <= 81
    # Kesin-sentetik: il kodu 82-99, gecersiz.
    synth = scenario.manifest["synthetic_plates"]
    assert len(synth) >= 1
    for plate in synth:
        assert not parse(plate).valid


def test_manifest_has_all_anomalies(scenario):
    a = scenario.manifest["anomalies"]
    assert set(a) == {"three_day_stay", "recurring_unregistered", "night_entry", "blacklisted"}
    assert a["three_day_stay"]["nights"] == 3
    assert len(a["recurring_unregistered"]["nights"]) == 5
    assert "T03:" in a["night_entry"]["entry_ts"]


def test_manifest_has_all_dirt_types(scenario):
    d = scenario.manifest["dirt"]
    assert set(d) >= {
        "clock_skew", "missing_exit", "ocr_error", "out_of_order", "duplicate"
    }
    assert d["missing_exit"]["visits_affected"] >= 1
    assert d["ocr_error"]["events_affected"] >= 1
    assert d["duplicate"]["events_replayed"] >= 1
    assert d["out_of_order"]["visits_affected"] >= 1
    assert d["clock_skew"]["events_affected"] >= 1


def test_duplicates_present_in_stream(scenario):
    ids = [g.payload.dedupe_key for g in scenario.stream]
    assert len(ids) > len(set(ids))  # en az bir tekrar teslim


def test_afternoon_checkin_peak(scenario):
    # Misafir girisleri ogleden sonraya yigilmali.
    hours = [
        g.payload.ts.astimezone(TR).hour
        for g in scenario.stream
        if g.kind == "guest" and g.role == "entry" and not g.dirt
    ]
    assert hours
    afternoon = sum(1 for h in hours if 13 <= h <= 20)
    assert afternoon / len(hours) > 0.6


def test_dirt_config_scales(scenario):
    quiet = generate(
        seed=SEED, start=date(2026, 3, 1), days=60, size=150,
        dirt_config=DirtConfig(missing_exit_rate=0.0, duplicate_rate=0.0,
                               ocr_error_rate=0.0, out_of_order_rate=0.0),
    )
    ids = [g.payload.dedupe_key for g in quiet.stream]
    assert len(ids) == len(set(ids))  # tekrar yok
    assert quiet.manifest["dirt"]["missing_exit"]["visits_affected"] == 0
