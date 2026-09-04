"""Test fixtures.

DB testleri gercek bir Postgres'e (pgvector) baglanir. `DATABASE_URL` ya da
`TEST_DATABASE_URL` env'i ile hedef verilir; ulasilamazsa DB testleri skip
edilir (DB gerektirmeyen testler calismaya devam eder).

Lokal:   docker compose up -d db   (ardindan ayri bir kervansaray_test DB'si)
CI:      services.postgres (bkz. .github/workflows/ci.yml)
"""
from __future__ import annotations

import os

_DEFAULT = "postgresql+psycopg://kervansaray:kervansaray@localhost:5432/kervansaray_test"
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", _DEFAULT))
os.environ.setdefault("LOG_TO_FILE", "false")
os.environ.setdefault("METRICS_ENABLED", "false")

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from kervansaray.config import settings  # noqa: E402
from kervansaray.db import sessionmaker_for  # noqa: E402
from tests._helpers import build_schema, truncate_all  # noqa: E402


def _probe_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(_probe_url(), future=True, connect_args={"connect_timeout": 3})
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Postgres yok: {exc}", allow_module_level=True)

    build_schema(eng)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_events"))
    from kervansaray.db import Base

    Base.metadata.drop_all(eng, checkfirst=True)


@pytest.fixture
def db(engine):
    truncate_all(engine)
    session = sessionmaker_for(engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(engine):
    truncate_all(engine)
    from kervansaray.api import create_app

    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c
