"""Alembic migration'i gercekten uygulaniyor mu (upgrade/downgrade/upgrade).

Bu test paylasilan semayi bozar; fixture teardown'da modelden yeniden kurar,
boylece sonraki DB testleri etkilenmez.
"""
import os

import pytest
from sqlalchemy import inspect, text

from kervansaray.config import settings
from tests._helpers import build_schema

_EXPECTED_TABLES = {
    "persons", "vehicles", "registrations", "events",
    "sessions", "notes", "daily_summaries", "alembic_version",
}


def _alembic_cfg():
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg


@pytest.fixture
def migration_engine(engine):
    # tertemiz sema ile basla
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    try:
        yield engine
    finally:
        # paylasilan semayi geri yukle
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        build_schema(engine)


def test_upgrade_downgrade_upgrade(migration_engine):
    from alembic import command

    os.environ["DATABASE_URL"] = settings.DATABASE_URL
    cfg = _alembic_cfg()

    command.upgrade(cfg, "head")
    insp = inspect(migration_engine)
    assert _EXPECTED_TABLES <= set(insp.get_table_names())
    assert "v_events" in insp.get_view_names()

    command.downgrade(cfg, "base")
    assert "events" not in inspect(migration_engine).get_table_names()

    command.upgrade(cfg, "head")
    assert _EXPECTED_TABLES <= set(inspect(migration_engine).get_table_names())
