"""add query_log table

Revision ID: 0004_add_query_log
Revises: 0003_add_title
Create Date: 2026-09-11

Admin dashboard icin: /api/query ucuna gelen her soru (metin + zaman) burada
tutulur. `Demoyu Sıfırla` (reset_demo) bu tabloya dokunmaz - demo verisi
degil, admin audit verisi.

Idempotent (kervansaray-ops/SKILL.md "Migration checklist"): `0001_initial`
Base.metadata.create_all ile calisir - `QueryLog` artik modellerde oldugu
icin sifirdan bir `alembic upgrade head` calistiginda tablo zaten 0001'de
olusuyor. IF NOT EXISTS / IF EXISTS, hem bu sifirdan senaryoyu hem de canli
(0003'te duran) DB'nin gercekten yeni tablo almasi gereken senaryoyu kapsar.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_add_query_log"
down_revision: str | None = "0003_add_title"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS query_log (
            id SERIAL PRIMARY KEY,
            query_text VARCHAR(500) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_query_log_created_at ON query_log (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS query_log")
