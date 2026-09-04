"""docs/event-contract.v1.json dosyasini EventV1 modelinden uretir.

    python -m kervansaray.events.export_schema

Sozlesme degistiginde bu calistirilir ve ciktisi commit'lenir. CI,
checked-in dosyanin modelle senkron oldugunu test_event_schema.py ile
dogrular.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import EventV1

_OUT = Path(__file__).resolve().parents[3] / "docs" / "event-contract.v1.json"

_META = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://yagizakkaya.com.tr/kervansaray/event-contract.v1.json",
    "title": "Kervansaray Event Contract v1.0",
    "description": (
        "Track A (vision) -> Track B (store+query) arasindaki tek dikis. "
        "Kaynak: docs/PROJECT_BRIEF.md S6. Uretilmis dosya - elle duzenleme; "
        "kaynak src/kervansaray/events/schema.py:EventV1."
    ),
}


def build() -> dict:
    return {**EventV1.model_json_schema(), **_META}


def main() -> None:
    _OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
