"""Engine ve session yonetimi.

`settings.DATABASE_URL` bir psycopg (v3) DSN'i olmali. `postgresql://` ve
`postgresql+psycopg://` ikisi de kabul edilir; ilki normalize edilir.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from kervansaray.config import settings

_engine: Engine | None = None


def _normalize_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Ulasilamayan bir DB'nin sureci sonsuza kadar bloklamamasi icin.
_CONNECT_ARGS = {"connect_timeout": 10}


def get_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Surec genelinde tek engine (url verilmezse)."""
    global _engine
    if url is not None:
        return create_engine(
            _normalize_url(url), echo=echo, pool_pre_ping=True, future=True,
            connect_args=_CONNECT_ARGS,
        )
    if _engine is None:
        _engine = create_engine(
            _normalize_url(settings.DATABASE_URL), echo=echo, pool_pre_ping=True, future=True,
            connect_args=_CONNECT_ARGS,
        )
    return _engine


def sessionmaker_for(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Transaction sinirli session; hata olursa rollback."""
    factory = sessionmaker_for(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
