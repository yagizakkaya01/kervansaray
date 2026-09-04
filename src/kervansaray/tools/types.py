"""Tool katmani ortak tipleri (PROJECT_BRIEF S3.2/S3.3).

Her tool sonucu provenance tasir: hangi cagri, arkasindaki event_id'ler.
"Narration is convenience; the table is the truth" - `rows` gercek, LLM
metni degil.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

# Modele donen satir tavani (S3.3). Ustunde aggregate cagrisina zorlanir.
MAX_ROWS = 50


def jsonable(value: Any) -> Any:
    """DB satir degerlerini JSON-guvenli hale getir (LLM'e / API'ye donmeden)."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return value.value
    return value


def json_row(mapping: Any) -> dict[str, Any]:
    return {k: jsonable(v) for k, v in dict(mapping).items()}


@dataclass
class ToolResult:
    tool: str
    params: dict[str, Any]
    rows: list[dict[str, Any]] = field(default_factory=list)
    scalar: Any = None
    truncated: bool = False
    event_ids: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "params": self.params,
            "rows": self.rows,
            "scalar": self.scalar,
            "truncated": self.truncated,
            "event_ids": self.event_ids,
            "note": self.note,
        }
