"""add contact to persons

Revision ID: 0002_add_contact
Revises: 0001_initial
Create Date: 2026-09-09

Not: 0001 semayi canli modelden (Base.metadata.create_all) kurdugu icin
`contact` kolonu tertemiz kurulumda zaten var olabilir. Bu yuzden idempotent
(IF NOT EXISTS) yazildi -> `alembic upgrade head` bastan calisir.
"""
from __future__ import annotations

from alembic import op

revision: str = "0002_add_contact"
down_revision: str | None = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE persons ADD COLUMN IF NOT EXISTS contact VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE persons DROP COLUMN IF EXISTS contact")
