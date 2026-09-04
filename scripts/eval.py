"""Altin set eval harness CLI (ROADMAP Faz 3 / PROJECT_BRIEF S9).

    python scripts/eval.py              # DATABASE_URL'e karsi kosar
    python scripts/eval.py --build      # once eval/gold_set.jsonl'i yeniden uret

Sabit sentetik senaryoyu kurar, populasyonu + olaylari ephemeral bir semaya
yukler, her altin sorunun beklenen tool cagrisini calistirir ve tek bir
dogruluk sayisi raporlar.

Postgres yoksa (DATABASE_URL erisilemez) atlar ve 0 doner - CI'da eval job'i
kendi Postgres servisiyle kosar.
"""
from __future__ import annotations

import sys

from eval import build as gold_build
from eval import runner
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from kervansaray.db import get_engine, sessionmaker_for
from kervansaray.db.views import rebuild_schema
from kervansaray.ingest import ingest_event
from kervansaray.synth.population import persist


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--build" in argv:
        gold_build.main()

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        print(f"eval: Postgres yok ({exc}). Atlaniyor.")
        return 0

    rebuild_schema(engine)
    scenario = gold_build.build_scenario()
    session = sessionmaker_for(engine)()
    try:
        persist(session, scenario.population)
        session.flush()
        for payload in scenario.payloads():
            ingest_event(session, payload)
        session.commit()
        result = runner.run(session)
    finally:
        session.close()

    print(result.summary())
    # Faz 3 bari: tool katmani altin oracle'a karsi %100 dogru olmali.
    return 0 if result.correct == result.scored else 1


if __name__ == "__main__":
    sys.exit(main())
