"""İnsan onay kuyruğu API uçları (ROADMAP Faz 8 & PROJECT_BRIEF §3.8).

Bulanık eşleşen (edit distance 1, MatchStatus.pending) plakalar otomatik
kabul edilmez; operatör onayına kuyruklanır.
  - GET  /api/review: Bekleyen onay listesi
  - POST /api/review/<event_id>/approve: Adayı kabul et (MatchStatus.fuzzy)
  - POST /api/review/<event_id>/reject: Adayı reddet (MatchStatus.unmatched)
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from kervansaray.db import session_scope
from kervansaray.db.models import Event, MatchStatus, Session
from kervansaray.logging import log

bp = Blueprint("review", __name__, url_prefix="/api/review")


@bp.get("")
def list_pending():
    """Operatör onayı bekleyen bulanık plaka olaylarını listeler."""
    limit = min(int(request.args.get("limit", 50)), 100)
    with session_scope() as db:
        stmt = (
            select(Event)
            .where(Event.match_status == MatchStatus.pending)
            .order_by(Event.ts.desc())
            .limit(limit)
        )
        events = list(db.scalars(stmt))

        pending = []
        for ev in events:
            cand = ev.candidate_vehicle
            cand_person = cand.person if cand else None
            pending.append(
                {
                    "event_id": ev.event_id,
                    "ts": ev.ts.isoformat(),
                    "direction": ev.direction.value,
                    "camera_id": ev.camera_id,
                    "raw_plate": ev.raw_plate,
                    "canonical_plate": ev.canonical_plate,
                    "crop_ref": ev.crop_ref,
                    "match_score": ev.match_score,
                    "candidate_vehicle_id": ev.candidate_vehicle_id,
                    "candidate_plate": cand.plate if cand else None,
                    "candidate_owner": cand_person.name if cand_person else None,
                    "candidate_kind": cand_person.kind.value if cand_person else None,
                    "candidate_is_blacklisted": cand.is_blacklisted if cand else False,
                }
            )

    return jsonify({"count": len(pending), "pending": pending}), 200


@bp.post("/<event_id>/approve")
def approve_candidate(event_id: str):
    """Operatör önerilen bulanık plaka adayını onaylar."""
    with session_scope() as db:
        ev = db.scalar(select(Event).where(Event.event_id == event_id))
        if ev is None:
            return jsonify({"error": "Olay bulunamadı"}), 404
        if ev.match_status != MatchStatus.pending:
            return jsonify({"error": f"Olay onay bekleyen durumda değil: {ev.match_status}"}), 400

        # Aday aracı bağla
        ev.match_status = MatchStatus.fuzzy
        ev.vehicle_id = ev.candidate_vehicle_id
        if ev.candidate_vehicle:
            ev.canonical_plate = ev.candidate_vehicle.plate

        # İlişkili açık veya tamamlanmış Session varsa vehicle_id ve plakayı senkronize et
        sessions = list(
            db.scalars(
                select(Session).where(
                    (Session.entry_event_id == ev.id) | (Session.exit_event_id == ev.id)
                )
            )
        )
        for s in sessions:
            s.vehicle_id = ev.vehicle_id
            s.canonical_plate = ev.canonical_plate

        log.info(
            "Event review approved event_id=%s raw_plate=%s vehicle_id=%s plate=%s",
            event_id,
            ev.raw_plate,
            ev.vehicle_id,
            ev.canonical_plate,
        )
        return jsonify(
            {
                "ok": True,
                "event_id": event_id,
                "status": ev.match_status.value,
                "plate": ev.canonical_plate,
                "vehicle_id": ev.vehicle_id,
            }
        ), 200


@bp.post("/<event_id>/reject")
def reject_candidate(event_id: str):
    """Operatör önerilen adayı reddeder; araç kayıtsız (unmatched) olarak işaretlenir."""
    with session_scope() as db:
        ev = db.scalar(select(Event).where(Event.event_id == event_id))
        if ev is None:
            return jsonify({"error": "Olay bulunamadı"}), 404
        if ev.match_status != MatchStatus.pending:
            return jsonify({"error": f"Olay onay bekleyen durumda değil: {ev.match_status}"}), 400

        ev.match_status = MatchStatus.unmatched
        ev.candidate_vehicle_id = None

        log.info("Event review rejected event_id=%s raw_plate=%s", event_id, ev.raw_plate)
        return jsonify(
            {
                "ok": True,
                "event_id": event_id,
                "status": ev.match_status.value,
            }
        ), 200
