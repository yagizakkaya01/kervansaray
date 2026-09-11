"""Altin set + eval harness (PROJECT_BRIEF S9, ROADMAP Faz 3).

- eval/gold_set.jsonl commit'lenmis hali modelle senkron (drift guard)
- kategori dagilimi dengeli, tum toollar temsil ediliyor
- tool katmani altin oracle'a karsi %100 dogru (Faz 3 bari)
"""
import json

import pytest
from eval import build as gold_build
from eval import runner
from eval.gold import GOLD, categories

from kervansaray.db.views import rebuild_schema


def test_gold_set_is_wellformed():
    assert 40 <= len(GOLD) <= 60
    ids = [q.id for q in GOLD]
    assert len(ids) == len(set(ids))
    tools = {q.tool for q in GOLD}
    assert tools == {
        "aggregate_events", "query_events", "vehicle_history",
        "find_anomalies", "occupancy", "decline", "search_notes",
        "registry_summary",
    }
    cats = categories()
    assert cats["decline"] >= 3  # guardrail sorulari


def test_checked_in_gold_set_matches_rebuild():
    """eval/gold_set.jsonl guncel mi (CI guvencesi)."""
    committed = [json.loads(line) for line in runner.GOLD_SET.read_text(
        encoding="utf-8"
    ).splitlines() if line.strip()]
    rebuilt = gold_build.build()
    rebuilt_norm = [json.loads(json.dumps(r, sort_keys=True)) for r in rebuilt]
    assert committed == rebuilt_norm, (
        "eval/gold_set.jsonl eski - yeniden uret: python -m eval.build"
    )


@pytest.fixture
def loaded_eval_db(engine):
    rebuild_schema(engine)
    from kervansaray.db import sessionmaker_for

    s = sessionmaker_for(engine)()
    gold_build.seed_eval_db(s)
    try:
        yield s
    finally:
        s.close()
        rebuild_schema(engine)


def test_tool_layer_matches_gold_oracle(loaded_eval_db):
    result = runner.run(loaded_eval_db)
    assert result.scored >= 35
    assert result.correct == result.scored, "\n" + result.summary()


def test_eval_runner_with_llm_declines():
    from unittest.mock import MagicMock, patch

    mock_db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "response": "[DECLINED] Bu konu otopark sistemi kapsamı dışındadır.",
        "function_call": None,
        "provider": "mock",
    }

    gold_declines = [
        {
            "id": "dec-01",
            "category": "decline",
            "question": "Bugun hava nasil?",
            "tool": "decline",
            "expected": {"decline": True},
            "params": {},
        },
        {
            "id": "dec-02",
            "category": "decline",
            "question": "Sarki soyle",
            "tool": "decline",
            "expected": {"decline": True},
            "params": {},
        },
    ]

    with patch("eval.runner.load_gold", return_value=gold_declines):
        res = runner.run(mock_db, with_llm=True, client=mock_client)
        assert res.scored == 2
        assert res.correct == 2
        assert res.deferred == 0

