"""Olay uclari: ingest (POST) ve okuma (GET, read-only).

GET yalnizca `v_events` denormalize view'una bakar - ham tablolar expose
edilmez (PROJECT_BRIEF S3.2/S3.3).
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import text

from kervansaray.db import session_scope
from kervansaray.events import EventV1
from kervansaray.ingest import ingest_event
from kervansaray.logging import log
from kervansaray.observability import EVENTS_DUPLICATE, EVENTS_INGESTED

bp = Blueprint("events", __name__)

_MAX_ROWS = 200


@bp.post("/events")
def post_event():
    raw = request.get_json(silent=True)
    if raw is None:
        return jsonify({"error": "gecersiz JSON govdesi"}), 400

    try:
        payload = EventV1.model_validate(raw)
    except ValidationError as exc:
        detail = exc.errors(include_context=False, include_url=False, include_input=False)
        return jsonify({"error": "sozlesme dogrulamasi basarisiz", "detail": detail}), 422

    with session_scope() as db:
        result = ingest_event(db, payload)

    if result.duplicate:
        EVENTS_DUPLICATE.inc()
        log.event(payload.plate, payload.direction, f"{result.match_status} (dup)")
        return jsonify(_result_body(result)), 200

    EVENTS_INGESTED.labels(payload.direction, result.match_status).inc()
    log.event(payload.plate, payload.direction, str(result.match_status))
    return jsonify(_result_body(result)), 201


@bp.get("/events")
def list_events():
    q = request.args
    filters = ["1=1"]
    params: dict[str, object] = {}

    if plate := q.get("plate"):
        from kervansaray.text.plates import canonicalize

        filters.append("plate = :plate")
        params["plate"] = canonicalize(plate)
    if start := _parse_ts(q.get("start")):
        filters.append("ts >= :start")
        params["start"] = start
    if end := _parse_ts(q.get("end")):
        filters.append("ts < :end")
        params["end"] = end
    if direction := q.get("direction"):
        filters.append("direction = :direction")
        params["direction"] = direction
    if status := q.get("match_status"):
        filters.append("match_status = :status")
        params["status"] = status

    limit = min(_int(q.get("limit"), default=50), _MAX_ROWS)
    params["limit"] = limit

    sql = text(
        f"SELECT * FROM v_events WHERE {' AND '.join(filters)} "  # noqa: S608 - filtreler sabit
        "ORDER BY ts DESC LIMIT :limit"
    )
    with session_scope() as db:
        rows = [dict(r) for r in db.execute(sql, params).mappings()]

    return jsonify({"count": len(rows), "limit": limit, "events": rows}), 200


# ----------------------------------------------------------------------
def _result_body(result) -> dict:
    return {
        "event_row_id": result.event_row_id,
        "event_id": result.event_id,
        "duplicate": result.duplicate,
        "match_status": str(result.match_status),
        "vehicle_id": result.vehicle_id,
        "session_id": result.session_id,
        "session_closed": result.session_closed,
    }


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _int(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
