"""Turetilmis view'lar - tek kaynak.

`v_events`: tool katmaninin gorecegi denormalize yuzey (PROJECT_BRIEF S3.2).
Ham normalize tablolar expose edilmez. Alembic migration'i, test fikstürleri
ve eval harness'i bu ayni tanimi kullanir.
"""
from __future__ import annotations

from sqlalchemy import Connection, Engine, text

from .base import Base

V_EVENTS_SQL = """
CREATE VIEW v_events AS
SELECT
    e.id AS event_row_id, e.event_id AS event_id, e.ts AS ts, e.direction AS direction,
    e.canonical_plate AS plate, e.raw_plate AS raw_plate, e.plate_confidence AS plate_confidence,
    e.match_status AS match_status, e.match_score AS match_score, e.vehicle_id AS vehicle_id,
    v.label AS vehicle_label, COALESCE(v.is_blacklisted, FALSE) AS is_blacklisted,
    p.id AS person_id, p.name AS person_name, p.kind AS person_kind, p.room_no AS room_no,
    EXISTS (
        SELECT 1 FROM registrations r
        WHERE r.vehicle_id = e.vehicle_id AND r.valid_from <= e.ts
          AND (r.valid_to IS NULL OR r.valid_to >= e.ts)
    ) AS registered,
    e.device_id AS device_id, e.camera_id AS camera_id, e.track_id AS track_id,
    e.crop_ref AS crop_ref, e.model_version AS model_version, e.created_at AS ingested_at
FROM events e
LEFT JOIN vehicles v ON v.id = e.vehicle_id
LEFT JOIN persons  p ON p.id = v.person_id;
"""


def create_views(conn: Connection) -> None:
    conn.execute(text(V_EVENTS_SQL))


def drop_views(conn: Connection) -> None:
    conn.execute(text("DROP VIEW IF EXISTS v_events"))


def rebuild_schema(engine: Engine) -> None:
    """Modelden tertemiz sema: extension + drop/create tablolar + view.

    Test fikstürleri ve eval harness'i kullanir (Alembic'in yaptigi isin
    programatik esdegeri; migration testleri ayrica gercek upgrade'i kosar).
    """
    from . import models as _models  # noqa: F401  metadata'yi doldurur

    with engine.begin() as conn:
        drop_views(conn)
    Base.metadata.drop_all(engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        create_views(conn)
