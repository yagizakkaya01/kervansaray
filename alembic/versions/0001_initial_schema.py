"""initial schema (PROJECT_BRIEF S7) + v_events view

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-04

Ilk migration modeli tek kaynak kabul eder: pgvector extension'i kurar,
Base.metadata.create_all ile S7 tablolarini olusturur, ardindan tool
katmaninin gorecegi tek yuzey olan v_events denormalize view'unu tanimlar
(S3.2 - ham tablolar expose edilmez).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from kervansaray.db import Base
from kervansaray.db import models as _models  # noqa: F401

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


V_EVENTS = """
CREATE VIEW v_events AS
SELECT
    e.id                              AS event_row_id,
    e.event_id                        AS event_id,
    e.ts                              AS ts,
    e.direction                       AS direction,
    e.canonical_plate                 AS plate,
    e.raw_plate                       AS raw_plate,
    e.plate_confidence                AS plate_confidence,
    e.match_status                    AS match_status,
    e.match_score                     AS match_score,
    e.vehicle_id                      AS vehicle_id,
    v.label                           AS vehicle_label,
    COALESCE(v.is_blacklisted, FALSE) AS is_blacklisted,
    p.id                              AS person_id,
    p.name                            AS person_name,
    p.kind                            AS person_kind,
    p.room_no                         AS room_no,
    EXISTS (
        SELECT 1 FROM registrations r
        WHERE r.vehicle_id = e.vehicle_id
          AND r.valid_from <= e.ts
          AND (r.valid_to IS NULL OR r.valid_to >= e.ts)
    )                                 AS registered,
    e.device_id                       AS device_id,
    e.camera_id                       AS camera_id,
    e.track_id                        AS track_id,
    e.crop_ref                        AS crop_ref,
    e.model_version                   AS model_version,
    e.created_at                      AS ingested_at
FROM events e
LEFT JOIN vehicles v ON v.id = e.vehicle_id
LEFT JOIN persons  p ON p.id = v.person_id;
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind, checkfirst=False)
    op.execute(V_EVENTS)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP VIEW IF EXISTS v_events")
    Base.metadata.drop_all(bind=bind, checkfirst=False)
    op.execute("DROP EXTENSION IF EXISTS vector")
