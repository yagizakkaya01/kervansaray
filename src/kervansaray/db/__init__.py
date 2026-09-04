"""Veritabani katmani: engine, session factory, ORM modelleri.

Postgres + pgvector (docker-compose `db` servisi). Sema Alembic ile
yonetilir (alembic/versions/). Bkz. docs/PROJECT_BRIEF.md S7,
docs/ROADMAP.md Faz 1.
"""
from __future__ import annotations

from .base import Base
from .engine import get_engine, session_scope, sessionmaker_for

__all__ = ["Base", "get_engine", "sessionmaker_for", "session_scope"]
