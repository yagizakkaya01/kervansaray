"""LLM tarafindan secilen tool cagrilarini calistiran guvenli dispatcher (PROJECT_BRIEF S3.2/S3.3).

Gelen parametre tiplerini (ISO string -> datetime, plaka buyuk harf vb.) dogrular,
uygun fonksiyonu calistirir ve standart ToolResult dondurur.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DbSession

from kervansaray.text.plates import canonicalize

from .anomalies import find_anomalies
from .events import aggregate_events, query_events
from .notes import search_notes
from .types import MAX_ROWS, ToolResult
from .vehicles import occupancy, vehicle_history

TOOLS = {
    "query_events": query_events,
    "aggregate_events": aggregate_events,
    "vehicle_history": vehicle_history,
    "find_anomalies": find_anomalies,
    "occupancy": occupancy,
    "search_notes": search_notes,
}


def _parse_ts(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).strip()) if val else None
    except (ValueError, TypeError):
        return None


def _parse_range(args: dict[str, Any]) -> tuple[datetime, datetime] | None:
    s, e = _parse_ts(args.get("start")), _parse_ts(args.get("end"))
    return (s, e) if s and e else None


def dispatch_tool(
    db: DbSession,
    name: str,
    args: dict[str, Any],
    *,
    as_of: datetime | None = None,
) -> ToolResult:
    """Modelin belirledigi tool cagrisini calistirir."""
    if name not in TOOLS:
        return ToolResult(
            tool=name,
            params=args,
            note=f"Bilinmeyen tool: {name}. Gecerli tool'lar: {list(TOOLS.keys())}",
        )

    fn = TOOLS[name]

    try:
        if name == "query_events":
            rng = _parse_range(args)
            if not rng:
                return ToolResult(
                    tool=name, params=args, note="start ve end zorunlu ISO zaman olmalidir.",
                )
            return fn(
                db,
                start=rng[0],
                end=rng[1],
                plate=args.get("plate"),
                direction=args.get("direction"),
                registered=args.get("registered"),
                person=args.get("person"),
                person_kind=args.get("person_kind"),
                limit=int(args.get("limit", MAX_ROWS)),
            )

        if name == "aggregate_events":
            rng = _parse_range(args)
            if not rng:
                return ToolResult(
                    tool=name, params=args, note="start ve end zorunlu ISO zaman olmalidir.",
                )
            return fn(
                db,
                start=rng[0],
                end=rng[1],
                group_by=args.get("group_by"),
                metric=args.get("metric", "count"),
                direction=args.get("direction"),
                registered=args.get("registered"),
                plate=args.get("plate"),
                person_kind=args.get("person_kind"),
            )

        if name == "vehicle_history":
            plate = args.get("plate", "")
            if not plate:
                return ToolResult(tool=name, params=args, note="plate parametresi zorunludur.")
            return fn(db, plate=canonicalize(plate))

        if name == "find_anomalies":
            rule = args.get("rule", "")
            rng = _parse_range(args)
            if not rule or not rng:
                return ToolResult(tool=name, params=args, note="rule, start ve end zorunludur.")
            return fn(
                db,
                rule=rule,
                start=rng[0],
                end=rng[1],
                min_visits=int(args.get("min_visits", 3)),
                overstay_hours=int(args.get("overstay_hours", 48)),
            )

        if name == "occupancy":
            return fn(db, as_of=_parse_ts(args.get("as_of")) or as_of)

        if name == "search_notes":
            query = str(args.get("query", "")).strip()
            if not query:
                return ToolResult(tool=name, params=args, note="query parametresi zorunludur.")
            return fn(
                db,
                query=query,
                author=args.get("author"),
                limit=int(args.get("limit", 10)),
            )

    except Exception as exc:  # noqa: BLE001
        return ToolResult(tool=name, params=args, note=f"Tool calistirma hatasi: {exc}")

    return ToolResult(tool=name, params=args, note=f"Calistirilamadi: {name}")
