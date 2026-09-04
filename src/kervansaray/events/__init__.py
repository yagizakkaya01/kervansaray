"""Olay sozlesmesi (event contract).

Track A (goruntu) ile Track B (depo+sorgu) arasindaki tek dikis.
Bkz. docs/PROJECT_BRIEF.md S6, docs/event-contract.v1.json
"""

from .schema import SCHEMA_VERSION, Direction, EventV1

__all__ = ["EventV1", "Direction", "SCHEMA_VERSION"]
