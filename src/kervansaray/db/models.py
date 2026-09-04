"""ORM modelleri - PROJECT_BRIEF S7 semasinin ilk kesiti.

Tasarim kurallari (S7):
  - Kisi ve plaka verisi kendi tablolarinda, `events`'ten ID ile referanslanir.
    Bu, ileride pseudonymisation / sifreleme / retention'i tek tablo degisikligi
    yapar (S14) - simdiden korunur.
  - `events` tipli kolonlara parse edilir, ham JSON blob saklanmaz (S6).
  - `sessions` turetilmistir (giris-cikis eslesmesi); acik session = exit_event_id NULL.
  - `v_events` denormalize view'u tool katmaninin gorecegi tek yuzeydir; ham
    tablolar expose edilmez (bu view Alembic migration'inda tanimli).
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

# notes / daily_summaries embedding boyutu. Faz 6'da embedding modeli
# secilince degisebilir (tek ALTER COLUMN migration'i). all-MiniLM-L6-v2 = 384.
EMBED_DIM = 384


class PersonKind(enum.StrEnum):
    guest = "guest"
    staff = "staff"
    vendor = "vendor"


class Direction(enum.StrEnum):
    entry = "entry"
    exit = "exit"


class MatchStatus(enum.StrEnum):
    exact = "exact"          # kanonik plaka bir araca birebir eslesti
    fuzzy = "fuzzy"          # bulanik eslesme bir insan tarafindan onaylandi
    unmatched = "unmatched"  # hicbir araca eslesmedi
    pending = "pending"      # bulanik aday; insan onayi bekliyor (S3.8)


def _pg_enum(e: type[enum.Enum], name: str) -> Enum:
    """Enum degerlerini (name degil value) kullanan Postgres ENUM tipi."""
    return Enum(e, name=name, values_callable=lambda x: [i.value for i in x])


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[PersonKind] = mapped_column(_pg_enum(PersonKind, "person_kind"), nullable=False)
    room_no: Mapped[str | None] = mapped_column(String(32))

    vehicles: Mapped[list[Vehicle]] = relationship(back_populates="person")


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Kanonik plaka (bkz. text/plates.py canonicalize): bosluksuz, buyuk harf.
    plate: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id", ondelete="SET NULL"))
    label: Mapped[str | None] = mapped_column(String(100))
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    person: Mapped[Person | None] = relationship(back_populates="vehicles")
    registrations: Mapped[list[Registration]] = relationship(back_populates="vehicle")


class Registration(Base, TimestampMixin):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vehicle: Mapped[Vehicle] = relationship(back_populates="registrations")

    __table_args__ = (Index("ix_registrations_vehicle_validity", "vehicle_id", "valid_from"),)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Idempotency anahtari (S6). Tekrar gonderim bu unique kisiti ile reddedilir.
    event_id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), unique=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="1.0")

    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    raw_plate: Mapped[str] = mapped_column(String(16), nullable=False)
    canonical_plate: Mapped[str] = mapped_column(String(16), nullable=False)
    plate_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    direction: Mapped[Direction] = mapped_column(_pg_enum(Direction, "direction"), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    crop_ref: Mapped[str | None] = mapped_column(String(512))
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    match_status: Mapped[MatchStatus] = mapped_column(
        _pg_enum(MatchStatus, "match_status"), nullable=False
    )
    match_score: Mapped[float | None] = mapped_column(Float)  # bulanik eslesmede 0-100
    # S3.8: bulanik aday insan onayina kuyruklanir. Onaylanana kadar vehicle_id
    # NULL kalir; aday burada tutulur (S7'ye ek - review queue icin gerekli).
    candidate_vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )

    vehicle: Mapped[Vehicle | None] = relationship(foreign_keys=[vehicle_id])
    candidate_vehicle: Mapped[Vehicle | None] = relationship(foreign_keys=[candidate_vehicle_id])

    __table_args__ = (
        Index("ix_events_plate_ts", "canonical_plate", "ts"),
        Index("ix_events_ts", "ts"),
        Index("ix_events_vehicle_ts", "vehicle_id", "ts"),
        # Ayni iz (track) + kamera birlikte bir arac gecisini tekillestirir (S6).
        Index("ix_events_track", "device_id", "camera_id", "track_id"),
    )


class Session(Base, TimestampMixin):
    """Turetilmis: bir giris olayinin bir cikis olayiyla eslesmesi.

    Uc bicim (S8 - gercek dunya kir):
      - normal      : entry + exit dolu
      - missing_exit: entry var, cikis kacirildi (S8'in #1 problemi). Yeni bir
        giris ayni arac icin acik session bulursa eskisi missing_exit=true olur.
      - missing_entry: cikis var, giris kacirildi ya da geç geldi.

    "Su an iceride kac arac?" = exit_event_id IS NULL AND missing_exit IS FALSE.

    Sirasi bozuk teslim edilen (cikis, girisinden once gelen) olaylar
    ingest/sessions.py icinde MERGE_WINDOW dahilinde geriye doldurularak
    mutabakat edilir; gun-olcegi gecikmeler disarida kalir.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    canonical_plate: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    entry_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE")
    )
    exit_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))

    entry_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Kapaninca (exit_ts - entry_ts) saniye; aksi halde NULL.
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    missing_entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_exit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    entry_event: Mapped[Event | None] = relationship(foreign_keys=[entry_event_id])
    exit_event: Mapped[Event | None] = relationship(foreign_keys=[exit_event_id])

    __table_args__ = (
        CheckConstraint(
            "entry_event_id IS NOT NULL OR exit_event_id IS NOT NULL",
            name="ck_sessions_has_endpoint",
        ),
        # "Su an iceride" sorgusu icin kismi index.
        Index(
            "ix_sessions_current",
            "vehicle_id",
            "canonical_plate",
            postgresql_where=text("exit_event_id IS NULL AND missing_exit IS FALSE"),
        ),
    )

    @property
    def is_current(self) -> bool:
        """Arac su an sahada mi (gercekten acik session)."""
        return self.exit_event_id is None and not self.missing_exit


class Note(Base, TimestampMixin):
    """Serbest metin: prosedur, olay raporu, vardiya notu, misafir tercihi (S3.6)."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Faz 6'da doldurulur (gece CPU batch). Simdilik NULL.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class DailySummary(Base, TimestampMixin):
    """Gece uretilen prose gun ozeti (S3.6). Faz 6."""

    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))

    __table_args__ = (UniqueConstraint("day", name="uq_daily_summaries_day"),)
