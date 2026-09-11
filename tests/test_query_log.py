"""Admin dashboard sorgu logu: /api/query soru metnini kaydediyor mu,
/api/internal/query-log dogru donuyor mu, MAX_ROWS budaniyor mu."""
from __future__ import annotations

from unittest.mock import patch

from kervansaray.db.models import QueryLog
from kervansaray.query_log import MAX_ROWS, record


def _mock_res(query_text: str) -> dict:
    return {
        "query": query_text,
        "status": "success",
        "narrative": "ok",
        "tool_call": None,
        "tool_result": None,
        "provider": "gemini",
        "cached": False,
    }


def test_post_query_records_question(client, db):
    with patch("kervansaray.api.routes_query.run_query") as mock_rq:
        mock_rq.side_effect = lambda q, *a, **kw: _mock_res(q)
        r = client.post("/api/query", json={"query": "bugun kac arac girdi?"})
        assert r.status_code == 200

    rows = db.query(QueryLog).all()
    assert len(rows) == 1
    assert rows[0].query_text == "bugun kac arac girdi?"


def test_internal_query_log_returns_newest_first(client, db):
    with patch("kervansaray.api.routes_query.run_query") as mock_rq:
        mock_rq.side_effect = lambda q, *a, **kw: _mock_res(q)
        client.post("/api/query", json={"query": "ilk soru"})
        client.post("/api/query", json={"query": "ikinci soru"})

    r = client.get("/api/internal/query-log")
    assert r.status_code == 200
    entries = r.get_json()["entries"]
    assert len(entries) == 2
    assert entries[0]["query_text"] == "ikinci soru"
    assert entries[1]["query_text"] == "ilk soru"
    assert "ts" in entries[0]


def test_record_prunes_beyond_max_rows(db):
    for i in range(MAX_ROWS + 5):
        record(db, f"soru {i}")
    db.commit()

    assert db.query(QueryLog).count() == MAX_ROWS
