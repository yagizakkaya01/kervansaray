"""Tool katmani ortak tipleri (PROJECT_BRIEF S3.2/S3.3).

Her tool sonucu provenance tasir: hangi cagri, arkasindaki event_id'ler.
"Narration is convenience; the table is the truth" - `rows` gercek, LLM
metni degil.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Modele donen satir tavani (S3.3). Ustunde aggregate cagrisina zorlanir.
MAX_ROWS = 50


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
