"""add title to persons + rebuild v_events with person_title

Revision ID: 0003_add_title
Revises: 0002_add_contact
Create Date: 2026-09-10

`persons.title` serbest metin unvan/rol alanini ekler. `v_events` bu alani
`person_title` olarak expose eder -> tool katmani (query_events person=) unvan
araması yapabilir. PostgreSQL'de view'a ALTER ile kolon eklenemedigi icin view
DROP + CREATE edilir; guncel tanim `kervansaray.db.views.V_EVENTS_SQL` (tek
kaynak). Downgrade, title'sız eski view tanimini inline tutar (donmus tarih).

Ayrica `unaccent` extension'i kurulur (Turkce aksan-duyarsiz ILIKE icin).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from kervansaray.db.views import V_EVENTS_SQL

revision: str = "0003_add_title"
down_revision: str | None = "0002_add_contact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 0002 sonrasi v_events tanimi (person_title YOK) - downgrade icin donmus kopya.
_V_EVENTS_SQL_PRE_TITLE = """
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


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # 0001 semayi canli modelden kurdugu icin kolon zaten var olabilir -> idempotent
    op.execute("ALTER TABLE persons ADD COLUMN IF NOT EXISTS title VARCHAR(100)")
    op.execute("DROP VIEW IF EXISTS v_events")
    op.execute(V_EVENTS_SQL)  # guncel: person_title dahil


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_events")
    op.execute("ALTER TABLE persons DROP COLUMN IF EXISTS title")
    op.execute(_V_EVENTS_SQL_PRE_TITLE)
