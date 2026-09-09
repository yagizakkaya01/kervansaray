"""add contact to persons

Revision ID: 0002_add_contact
Revises: 0001_initial
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_contact"
down_revision: str | None = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("contact", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("persons", "contact")
