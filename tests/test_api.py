"""Ingest API testleri (POST/GET /events, /healthz)."""
import json

from tests._helpers import make_event


def _post(client, event):
    return client.post(
        "/events", data=event.model_dump_json(), content_type="application/json"
    )


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_post_event_created_then_duplicate(client):
    ev = make_event(plate="34ABC123", direction="entry")
    r1 = _post(client, ev)
    assert r1.status_code == 201
    body = r1.get_json()
    assert body["duplicate"] is False
    assert body["match_status"] == "unmatched"

    r2 = _post(client, ev)
    assert r2.status_code == 200
    assert r2.get_json()["duplicate"] is True


def test_post_invalid_payload_is_422(client):
    bad = {"event_id": "not-a-uuid", "direction": "entry"}
    r = client.post("/events", data=json.dumps(bad), content_type="application/json")
    assert r.status_code == 422
    assert "detail" in r.get_json()


def test_post_tz_naive_ts_rejected(client):
    payload = make_event().model_dump(mode="json")
    payload["ts"] = "2026-09-03T14:00:00"  # tz yok
    r = client.post("/events", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 422


def test_get_events_reads_v_events_view(client):
    _post(client, make_event(plate="34ABC123", direction="entry", minutes=0))
    _post(client, make_event(plate="06XYZ99", direction="entry", minutes=5))

    r = client.get("/events?limit=10")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 2
    # v_events denormalize alanlari
    assert {"plate", "registered", "is_blacklisted", "person_name"} <= set(data["events"][0])

    r2 = client.get("/events?plate=34+abc+123")
    assert r2.get_json()["count"] == 1
    assert r2.get_json()["events"][0]["plate"] == "34ABC123"


def test_post_query_validation():
    from unittest.mock import MagicMock, patch

    from kervansaray.api import create_app

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    # 1. Invalid / non-JSON body
    r = c.post("/api/query", data="invalid", content_type="text/plain")
    assert r.status_code == 400

    # 2. Empty query
    r = c.post("/api/query", json={"query": ""})
    assert r.status_code == 400
    assert "boş olamaz" in r.get_json()["error"]

    r = c.post("/api/query", json={"query": "   "})
    assert r.status_code == 400

    # 3. Invalid as_of format
    r = c.post("/api/query", json={"query": "kac arac var?", "as_of": "gecersiz-tarih"})
    assert r.status_code == 400
    assert "Geçersiz 'as_of'" in r.get_json()["error"]

    # 4. Valid query with mocked run_query
    mock_res = {
        "query": "bugun kac arac girdi?",
        "status": "success",
        "narrative": "Bugün 12 araç girdi.",
        "tool_call": {"name": "aggregate_events", "args": {}},
        "tool_result": {"scalar": 12},
        "provider": "gemini",
        "cached": False,
    }
    with patch("kervansaray.api.routes_query.session_scope") as mock_scope, \
         patch("kervansaray.api.routes_query.run_query", return_value=mock_res) as mock_rq:
        mock_scope.return_value.__enter__.return_value = MagicMock()

        r = c.post("/api/query", json={"query": "bugun kac arac girdi?"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "success"
        assert data["narrative"] == "Bugün 12 araç girdi."
        assert data["tool_result"]["scalar"] == 12
        assert mock_rq.call_count == 1


def test_get_index_serves_frontend():
    from kervansaray.api import create_app

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    r = c.get("/")
    assert r.status_code == 200
    assert "Kervansaray" in r.get_data(as_text=True)
    assert "query-input" in r.get_data(as_text=True)


