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
from kervansaray.ingest import ingest_event
from kervansaray.synth.population import persist


def test_gold_set_is_wellformed():
    assert 40 <= len(GOLD) <= 60
    ids = [q.id for q in GOLD]
    assert len(ids) == len(set(ids))
    tools = {q.tool for q in GOLD}
    assert tools == {
        "aggregate_events", "query_events", "vehicle_history",
        "find_anomalies", "occupancy", "decline",
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

    scenario = gold_build.build_scenario()
    s = sessionmaker_for(engine)()
    persist(s, scenario.population)
    s.flush()
    for payload in scenario.payloads():
        ingest_event(s, payload)
    s.commit()
    try:
        yield s
    finally:
        s.close()
        rebuild_schema(engine)


def test_tool_layer_matches_gold_oracle(loaded_eval_db):
    result = runner.run(loaded_eval_db)
    assert result.scored >= 35
    assert result.correct == result.scored, "\n" + result.summary()
