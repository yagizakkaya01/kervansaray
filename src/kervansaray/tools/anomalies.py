"""find_anomalies (PROJECT_BRIEF S3.2, S8, S3.7).

Kurallar deterministik - bir kural motoru tarafindan da kullanilabilir (S3.7).
window = (start, end), yari-acik.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from .types import ToolResult

RULES = {"unregistered_recurring", "overstay", "blacklist", "night_entry"}

# Varsayilan esikler.
RECURRING_MIN_VISITS = 3
OVERSTAY_HOURS = 48
NIGHT_START_HOUR = 0
NIGHT_END_HOUR = 5


def find_anomalies(
    db: DbSession,
    *,
    rule: str,
    start: datetime,
    end: datetime,
    min_visits: int = RECURRING_MIN_VISITS,
    overstay_hours: int = OVERSTAY_HOURS,
) -> ToolResult:
    if rule not in RULES:
        raise ValueError(f"rule {RULES} icinden olmali: {rule}")
    fn = {
        "unregistered_recurring": _unregistered_recurring,
        "overstay": _overstay,
        "blacklist": _blacklist,
        "night_entry": _night_entry,
    }[rule]
    rows = fn(db, start, end, min_visits=min_visits, overstay_hours=overstay_hours)
    return ToolResult(
        tool="find_anomalies",
        params={"rule": rule, "start": start.isoformat(), "end": end.isoformat()},
        rows=rows,
        scalar=len(rows),
    )


def _unregistered_recurring(db, start, end, *, min_visits, **_):
    sql = text(
        """
        SELECT plate,
               count(*) FILTER (WHERE direction = 'entry') AS visits,
               min(ts) AS first_seen, max(ts) AS last_seen
        FROM v_events
        WHERE ts >= :start AND ts < :end AND match_status = 'unmatched'
        GROUP BY plate
        HAVING count(*) FILTER (WHERE direction = 'entry') >= :mv
        ORDER BY visits DESC, plate
        """
    )
    return [
        {
            "plate": r.plate, "visits": int(r.visits),
            "first_seen": r.first_seen.isoformat(), "last_seen": r.last_seen.isoformat(),
        }
        for r in db.execute(sql, {"start": start, "end": end, "mv": min_visits})
    ]


def _overstay(db, start, end, *, overstay_hours, **_):
    sql = text(
        """
        SELECT s.canonical_plate AS plate, s.entry_ts, s.exit_ts,
               s.duration_seconds, s.missing_exit,
               (s.exit_event_id IS NULL AND s.missing_exit IS FALSE) AS still_inside
        FROM sessions s
        WHERE s.entry_ts >= :start AND s.entry_ts < :end
          AND (
            s.duration_seconds > :secs
            OR (s.exit_event_id IS NULL AND s.missing_exit IS FALSE
                AND s.entry_ts < :end - (:secs * interval '1 second'))
          )
        ORDER BY s.entry_ts
        """
    )
    out = []
    for r in db.execute(
        sql, {"start": start, "end": end, "secs": overstay_hours * 3600}
    ):
        hours = (r.duration_seconds / 3600) if r.duration_seconds is not None else None
        out.append(
            {
                "plate": r.plate,
                "entry_ts": r.entry_ts.isoformat() if r.entry_ts else None,
                "exit_ts": r.exit_ts.isoformat() if r.exit_ts else None,
                "hours": round(hours, 1) if hours is not None else None,
                "still_inside": bool(r.still_inside),
            }
        )
    return out


def _blacklist(db, start, end, **_):
    sql = text(
        """
        SELECT plate, ts, direction
        FROM v_events
        WHERE ts >= :start AND ts < :end AND is_blacklisted IS TRUE
        ORDER BY ts
        """
    )
    return [
        {"plate": r.plate, "ts": r.ts.isoformat(), "direction": str(r.direction)}
        for r in db.execute(sql, {"start": start, "end": end})
    ]


def _night_entry(db, start, end, **_):
    sql = text(
        """
        SELECT plate, ts
        FROM v_events
        WHERE ts >= :start AND ts < :end AND direction = 'entry'
          AND extract(hour FROM ts AT TIME ZONE 'Europe/Istanbul') >= :h0
          AND extract(hour FROM ts AT TIME ZONE 'Europe/Istanbul') < :h1
        ORDER BY ts
        """
    )
    return [
        {"plate": r.plate, "ts": r.ts.isoformat()}
        for r in db.execute(
            sql, {"start": start, "end": end, "h0": NIGHT_START_HOUR, "h1": NIGHT_END_HOUR}
        )
    ]
