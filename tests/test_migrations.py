"""Alembic migration'i gercekten uygulaniyor mu (upgrade/downgrade/upgrade).

Bu test paylasilan semayi bozar; fixture teardown'da modelden yeniden kurar,
boylece sonraki DB testleri etkilenmez.
"""
import os

import pytest
from sqlalchemy import inspect, text

from kervansaray.config import settings
from kervansaray.db.engine import get_engine
from tests._helpers import build_schema

_EXPECTED_TABLES = {
    "persons", "vehicles", "registrations", "events",
    "sessions", "notes", "alembic_version",
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
        # Bu test tablo/view'lari DROP+CREATE ediyor (OID degisiyor). Uygulamanin
        # kendi paylasilan connection pool'unda (get_engine()) bu tablolara karsi
        # daha once hazirlanmis (psycopg auto-prepare) plan'lari olan bagli
        # connection'lar varsa, sonraki testler "cached plan must not change
        # result type" (psycopg.errors.FeatureNotSupported) hatasi alir. Havuzu
        # burada atarak sonraki testlerin taze connection almasini garantile.
        get_engine().dispose()


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
