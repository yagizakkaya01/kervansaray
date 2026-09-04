"""query_events + aggregate_events (PROJECT_BRIEF S3.2).

Tum sorgular `v_events` denormalize view'una gider - ham tablolar yok (S3.2).
Zaman araliklari yari-acik: [start, end).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from kervansaray.text.plates import canonicalize

from .types import MAX_ROWS, ToolResult, json_row

_DIRECTIONS = {"entry", "exit"}
_GROUP_BY = {"day", "hour", "direction", "match_status", "person_kind"}
_METRICS = {"count", "unique_plates"}


def query_events(
    db: DbSession,
    *,
    start: datetime,
    end: datetime,
    plate: str | None = None,
    direction: str | None = None,
    registered: bool | None = None,
    limit: int = MAX_ROWS,
) -> ToolResult:
    """Bir zaman araligindaki olay satirlari. En fazla MAX_ROWS; ustunde
    aggregate_events'e yonlendirilir."""
    params: dict = {"start": start, "end": end}
    where = ["ts >= :start", "ts < :end"]
    if plate:
        where.append("plate = :plate")
        params["plate"] = canonicalize(plate)
    if direction:
        _check(direction in _DIRECTIONS, f"direction 'entry'|'exit' olmali: {direction}")
        where.append("direction = :direction")
        params["direction"] = direction
    if registered is not None:
        where.append("registered = :registered")
        params["registered"] = registered

    capped = max(1, min(int(limit), MAX_ROWS))
    params["lim"] = capped + 1
    sql = text(
        f"SELECT * FROM v_events WHERE {' AND '.join(where)} "  # noqa: S608 - sabit parcalar
        "ORDER BY ts ASC LIMIT :lim"
    )
    rows = [json_row(r) for r in db.execute(sql, params).mappings()]
    truncated = len(rows) > capped
    rows = rows[:capped]
    return ToolResult(
        tool="query_events",
        params=_clean_params(params),
        rows=rows,
        truncated=truncated,
        event_ids=[r["event_id"] for r in rows],
        note="Satir tavani asildi - aggregate_events kullanin." if truncated else None,
    )


def aggregate_events(
    db: DbSession,
    *,
    metric: str,
    start: datetime,
    end: datetime,
    group_by: str | None = None,
    direction: str | None = None,
    registered: bool | None = None,
) -> ToolResult:
    """Sayim / benzersiz plaka; opsiyonel gruplama. Sonuc DB'de hesaplanir."""
    _check(metric in _METRICS, f"metric {_METRICS} icinden olmali: {metric}")
    _check(group_by is None or group_by in _GROUP_BY, f"gecersiz group_by: {group_by}")

    params: dict = {"start": start, "end": end}
    where = ["ts >= :start", "ts < :end"]
    if direction:
        _check(direction in _DIRECTIONS, f"gecersiz direction: {direction}")
        where.append("direction = :direction")
        params["direction"] = direction
    if registered is not None:
        where.append("registered = :registered")
        params["registered"] = registered

    agg = "count(*)" if metric == "count" else "count(DISTINCT plate)"
    grp = _group_expr(group_by)

    if grp is None:
        sql = text(f"SELECT {agg} AS v FROM v_events WHERE {' AND '.join(where)}")  # noqa: S608
        scalar = db.execute(sql, params).scalar_one()
        return ToolResult(
            tool="aggregate_events", params=_clean_params(params) | {"metric": metric},
            scalar=int(scalar),
        )

    sql = text(  # noqa: S608 - grp ve where sabit whitelist'ten
        f"SELECT {grp} AS g, {agg} AS v FROM v_events WHERE {' AND '.join(where)} "
        "GROUP BY g ORDER BY g"
    )
    rows = [{"group": _as_str(r.g), "value": int(r.v)} for r in db.execute(sql, params)]
    return ToolResult(
        tool="aggregate_events",
        params=_clean_params(params) | {"metric": metric, "group_by": group_by},
        rows=rows,
    )


# ----------------------------------------------------------------------
def _group_expr(group_by: str | None) -> str | None:
    return {
        None: None,
        "day": "(ts AT TIME ZONE 'Europe/Istanbul')::date",
        "hour": "extract(hour FROM ts AT TIME ZONE 'Europe/Istanbul')::int",
        "direction": "direction",
        "match_status": "match_status",
        "person_kind": "coalesce(person_kind::text, 'unknown')",
    }[group_by]


def _as_str(v: object) -> str:
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _clean_params(p: dict) -> dict:
    out = {k: v for k, v in p.items() if k != "lim"}
    for k in ("start", "end"):
        if k in out and hasattr(out[k], "isoformat"):
            out[k] = out[k].isoformat()
    return out


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)
