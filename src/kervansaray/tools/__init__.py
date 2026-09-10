"""Tipli, parametreli tool katmani (PROJECT_BRIEF S3.2).

LLM ham SQL yazmaz; bu kucuk fonksiyon kumesini cagirir. Her tool:
  - yalnizca `v_events` / turetilmis tablolar uzerinde okur (join hatasi yok)
  - sonucu DB hesaplar (LLM "gozle saymaz", S3.3)
  - provenance dondurur (cagri + event_id'ler)

Faz 3: fonksiyonlar + izole birim testleri. Faz 4: LLM'e baglama semasi,
few-shot, satir tavani zorlamasi, kapsam sinirlayici prompt bunlarin
uzerine eklenir.
"""
from __future__ import annotations

from .anomalies import RULES, find_anomalies
from .dispatcher import TOOLS, dispatch_tool
from .events import aggregate_events, query_events
from .notes import search_notes
from .registry import registry_summary
from .schemas import (
    FUNCTION_DECLARATIONS,
    GEMINI_FUNCTION_DECLARATIONS,
    OPENAI_TOOLS,
)
from .types import MAX_ROWS, ToolResult
from .vehicles import occupancy, vehicle_history

__all__ = [
    "TOOLS",
    "RULES",
    "MAX_ROWS",
    "ToolResult",
    "query_events",
    "aggregate_events",
    "vehicle_history",
    "find_anomalies",
    "occupancy",
    "search_notes",
    "registry_summary",
    "dispatch_tool",
    "FUNCTION_DECLARATIONS",
    "GEMINI_FUNCTION_DECLARATIONS",
    "OPENAI_TOOLS",
]
