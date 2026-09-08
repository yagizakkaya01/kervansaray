"""Tool semalari ve dispatcher birim testleri."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from kervansaray.llm.prompts import FEW_SHOT_EXAMPLES, build_system_prompt
from kervansaray.tools import (
    FUNCTION_DECLARATIONS,
    GEMINI_FUNCTION_DECLARATIONS,
    dispatch_tool,
)


def test_function_declarations_complete():
    names = {f["name"] for f in FUNCTION_DECLARATIONS}
    expected = {
        "query_events", "aggregate_events", "vehicle_history", "find_anomalies", "occupancy"
    }
    assert names == expected
    assert len(GEMINI_FUNCTION_DECLARATIONS) == 5


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
