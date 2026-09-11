"""initial schema (PROJECT_BRIEF S7) + v_events view

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-04

Ilk migration modeli tek kaynak kabul eder: Base.metadata.create_all ile
S7 tablolarini olusturur, ardindan tool katmaninin gorecegi tek yuzey olan
v_events denormalize view'unu tanimlar (S3.2 - ham tablolar expose edilmez).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from kervansaray.db import Base
from kervansaray.db import models as _models  # noqa: F401
from kervansaray.db.views import V_EVENTS_SQL

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # checkfirst=False kasitli: sifirdan bir upgrade'de bir tablo zaten varsa
    # (ör. iki migration ayni tabloyu olusturmaya calisirsa) bunu sessizce
    # yutmak yerine gurultuyle patlasin (kervansaray-ops/SKILL.md "Migration
    # checklist").
    Base.metadata.create_all(bind=bind, checkfirst=False)
    op.execute(V_EVENTS_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP VIEW IF EXISTS v_events")
    # checkfirst=True (upgrade() kasitli False kalir, yukarida): sonraki bir
    # migration (ör. 0004) Base.metadata'ya eklenmis bir tabloyu kendi
    # downgrade()'inde onceden DROP etmis olabilir (idempotent IF EXISTS) -
    # burasi checkfirst=False olsaydi o tabloyu tekrar DROP etmeye calisip
    # UndefinedTable ile patlardi. Var olmayan bir tabloyu sessizce atlamak
    # burada guvenli: create_all zaten sifirdan calisirken hepsini olusturuyor.
    Base.metadata.drop_all(bind=bind, checkfirst=True)
