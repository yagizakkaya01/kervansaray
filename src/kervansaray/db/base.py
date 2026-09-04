"""SQLAlchemy declarative base + ortak sutunlar."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Tum ORM modellerinin taban sinifi."""


class TimestampMixin:
    """created_at - kaydin DB'ye yazildigi an (UTC, timezone-aware)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
