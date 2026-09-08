"""Tool semalari ve dispatcher birim testleri."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from kervansaray.llm.prompts import FEW_SHOT_EXAMPLES, build_system_prompt
from kervansaray.tools import (
    FUNCTION_DECLARATIONS,
    GEMINI_FUNCTION_DECLARATIONS,
    OPENAI_TOOLS,
    dispatch_tool,
)


def test_function_declarations_complete():
    names = {f["name"] for f in FUNCTION_DECLARATIONS}
    expected = {
        "query_events", "aggregate_events", "vehicle_history",
        "find_anomalies", "occupancy", "search_notes",
    }
    assert names == expected
    assert len(GEMINI_FUNCTION_DECLARATIONS) == 6
    assert len(OPENAI_TOOLS) == 6
    assert OPENAI_TOOLS[0]["type"] == "function"

    # search_notes schema query icermeli
    notes_schema = next(f for f in FUNCTION_DECLARATIONS if f["name"] == "search_notes")
    props = notes_schema["parameters"]["properties"]
    assert "query" in props
    assert "author" in props
    assert "limit" in props


def test_dispatch_aggregate_events_with_filters(monkeypatch):
    db = MagicMock()
    mock_fn = MagicMock()
    monkeypatch.setitem(
        __import__("kervansaray.tools.dispatcher", fromlist=["TOOLS"]).TOOLS,
        "aggregate_events",
        mock_fn,
    )

    dispatch_tool(
        db,
        "aggregate_events",
        {
            "start": "2026-04-15T00:00:00+03:00",
            "end": "2026-04-16T00:00:00+03:00",
            "direction": "entry",
            "registered": True,
            "metric": "count",
        },
    )
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["direction"] == "entry"
    assert kwargs["registered"] is True
    assert kwargs["metric"] == "count"



def test_dispatch_unknown_tool():
    db = MagicMock()
    res = dispatch_tool(db, "unknown_tool", {})
    assert "Bilinmeyen tool" in str(res.note)


def test_dispatch_missing_params():
    db = MagicMock()
    res = dispatch_tool(db, "query_events", {})
    assert "start ve end zorunlu" in str(res.note)


def test_system_prompt_builder():
    prompt = build_system_prompt(
        as_of=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
        time_hint="test ipucu",
    )
    assert "2026-04-15" in prompt
    assert "test ipucu" in prompt
    assert "aggregate_events" in prompt
    assert "v_events" in prompt
    assert len(FEW_SHOT_EXAMPLES) >= 8
