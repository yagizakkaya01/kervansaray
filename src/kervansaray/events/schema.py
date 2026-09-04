"""Olay sozlesmesi v1.0 - Pydantic modeli.

docs/PROJECT_BRIEF.md S6'daki sozlesmenin makine-dogrulanabilir hali.
Bu model her seyin bagli oldugu tek artefakt; degistirmek iki tarafi da
etkiler (S2). Kirilma yaratan degisiklikte SCHEMA_VERSION artirilir ve
yeni bir model sinifi eklenir (EventV2), eski surum silinmez.

Pazarlik disi kurallar (S6):
  - event_id bir idempotency anahtaridir. Edge cihazi cevrimdisiyken
    olaylari tamponlar ve baglaninca tekrar gonderir; bu alan olmadan
    tekrarlar her sayimi sisirir.
  - Zaman damgalari daima timezone tasir. tz-naive ts reddedilir.
  - Arac izi (track) basina TEK olay - frame basina degil. track_id +
    (device_id, camera_id) birlikte bir izi tekillestirir.
  - Alanlar tipli; ham JSON blob olarak saklanmaz (S6/S7).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"

Direction = Literal["entry", "exit"]

# Turk plakasi: 2 rakam il kodu + 1-3 harf + 2-4 rakam (bkz. text/plates.py).
# Sozlesmede ham okuma tutulur; kanoniklestirme/dogrulama ingest sirasinda
# text.plates ile yapilir - burada sadece kabaca sekil kontrolu.
_PLATE_SHAPE = r"^[0-9]{2}[A-Za-z]{1,3}[0-9]{2,4}$"


class EventV1(BaseModel):
    """Tek bir arac hareketi (giris veya cikis)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = SCHEMA_VERSION

    # --- Kimlik / kaynak ---
    event_id: UUID = Field(description="Idempotency anahtari; edge cihazi uretir")
    device_id: str = Field(min_length=1, max_length=64)
    camera_id: str = Field(min_length=1, max_length=64)

    # --- Zaman ---
    ts: datetime = Field(description="Olay ani; timezone ZORUNLU")

    # --- Plaka okuma ---
    plate: str = Field(
        min_length=4, max_length=16,
        description="Ham OCR okumasi; bosluksuz. Kanoniklestirme ingest'te.",
    )
    plate_confidence: float = Field(ge=0.0, le=1.0)
    char_confidences: list[float] | None = Field(
        default=None, description="Karakter bazli guven; voting sonrasi (S4.1)",
    )

    # --- Hareket ---
    direction: Direction
    track_id: int = Field(ge=0, description="ByteTrack iz kimligi; iz basina tek olay")

    # --- Provenans ---
    crop_ref: str | None = Field(
        default=None, max_length=512,
        description="Plaka kirpimina referans (obje deposu URI'si)",
    )
    model_version: str = Field(min_length=1, max_length=64)

    # ------------------------------------------------------------------
    @field_validator("ts")
    @classmethod
    def _ts_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("ts timezone tasimali (tz-naive reddedilir)")
        return v

    @field_validator("plate")
    @classmethod
    def _plate_no_spaces(cls, v: str) -> str:
        cleaned = v.strip().replace(" ", "").replace("-", "").upper()
        if not cleaned:
            raise ValueError("plate bos olamaz")
        return cleaned

    @field_validator("char_confidences")
    @classmethod
    def _char_conf_range(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and any(not (0.0 <= c <= 1.0) for c in v):
            raise ValueError("char_confidences degerleri 0..1 araliginda olmali")
        return v

    # ------------------------------------------------------------------
    @property
    def ts_utc(self) -> datetime:
        """Depolama/karsilastirma icin UTC'ye normalize edilmis zaman."""
        return self.ts.astimezone(UTC)

    @property
    def dedupe_key(self) -> str:
        """Idempotency anahtari (event_id). Ingest bu deger uzerinde tekil."""
        return str(self.event_id)
