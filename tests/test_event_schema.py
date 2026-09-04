"""Olay sozlesmesi v1.0 testleri (PROJECT_BRIEF S6)."""
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kervansaray.events import EventV1
from kervansaray.events.schema import EventV1 as EventV1Direct

_TR = timezone(timedelta(hours=3))


def _valid_payload(**overrides) -> dict:
    base = {
        "event_id": str(uuid4()),
        "device_id": "jetson-01",
        "camera_id": "entry-1",
        "ts": datetime(2026, 9, 3, 14, 32, 7, tzinfo=_TR).isoformat(),
        "plate": "34ABC123",
        "plate_confidence": 0.94,
        "char_confidences": [0.99, 0.98, 0.71, 0.95, 0.99, 0.88, 0.92, 0.97],
        "direction": "entry",
        "track_id": 4127,
        "crop_ref": "s3://crops/b7f3a1e2.jpg",
        "model_version": "yolo-plate-v3",
    }
    base.update(overrides)
    return base


def test_valid_event_roundtrips():
    ev = EventV1.model_validate(_valid_payload())
    assert ev.schema_version == "1.0"
    assert ev.direction == "entry"
    assert ev.dedupe_key == str(ev.event_id)
    assert ev.ts_utc.tzinfo == UTC


def test_tz_naive_timestamp_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        EventV1.model_validate(_valid_payload(ts="2026-09-03T14:32:07"))


def test_plate_whitespace_and_dash_normalised():
    ev = EventV1.model_validate(_valid_payload(plate=" 34-abc 123 "))
    assert ev.plate == "34ABC123"


def test_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        EventV1.model_validate(_valid_payload(foo="bar"))


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_confidence_out_of_range_rejected(bad):
    with pytest.raises(ValidationError):
        EventV1.model_validate(_valid_payload(plate_confidence=bad))


def test_char_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError, match="0..1"):
        EventV1.model_validate(_valid_payload(char_confidences=[0.5, 1.4]))


def test_direction_enum_enforced():
    with pytest.raises(ValidationError):
        EventV1.model_validate(_valid_payload(direction="in"))


def test_schema_version_is_const():
    with pytest.raises(ValidationError):
        EventV1.model_validate(_valid_payload(schema_version="2.0"))


def test_optional_fields_may_be_absent():
    payload = _valid_payload()
    del payload["char_confidences"]
    del payload["crop_ref"]
    ev = EventV1.model_validate(payload)
    assert ev.char_confidences is None
    assert ev.crop_ref is None


def test_checked_in_json_schema_matches_model():
    """docs/event-contract.v1.json modelle senkron kalmali (CI guvencesi)."""
    checked_in = json.loads(Path("docs/event-contract.v1.json").read_text(encoding="utf-8"))
    live = EventV1Direct.model_json_schema()
    # $schema/$id/title/description uretici tarafinda elle eklenir; govdeyi karsilastir.
    for k in ("$schema", "$id", "title", "description"):
        checked_in.pop(k, None)
        live.pop(k, None)
    assert checked_in == live, (
        "docs/event-contract.v1.json guncel degil - yeniden uret: "
        "python -m kervansaray.events.export_schema"
    )
