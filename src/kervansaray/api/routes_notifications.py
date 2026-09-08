"""Bildirim API uçları: REST okuma ve SSE canlı akışı (ROADMAP Faz 7).

Ponytail:
  - WebSocket yerine HTTP-yerel Server-Sent Events (SSE: text/event-stream).
  - Sıfır ek kütüphane; Flask Response generator'ı + broker queue.
"""
from __future__ import annotations

import queue

from flask import Blueprint, Response, jsonify, request

from kervansaray.notifications import broker

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _parse_limit(raw: str | None, default: int = 50, max_limit: int = 100) -> int:
    if raw is None:
        return default
    val = int(raw)
    if val <= 0:
        raise ValueError("limit must be positive")
    return min(val, max_limit)


@bp.get("")
def list_notifications():
    """Son bildirimlerin listesini JSON olarak döner."""
    try:
        limit = _parse_limit(request.args.get("limit"))
    except ValueError:
        return jsonify({"error": "gecersiz limit parametresi"}), 400
    items = broker.get_recent(limit=limit)
    return jsonify({"count": len(items), "notifications": items}), 200


@bp.get("/stream")
def stream_notifications():
    """Server-Sent Events (SSE) ile canlı bildirim akışı."""
    q = broker.subscribe()
    if q is None:
        return jsonify({"error": "Maksimum eszamanli bildirim akisi limitine ulasildi"}), 503

    def event_stream():
        try:
            # İstemciye ilk bağlantı onayını gönder
            yield "event: connected\ndata: {\"status\": \"ok\"}\n\n"
            while True:
                try:
                    # Yeni bildirim bekle (15 sn zaman aşımı ile)
                    notification = q.get(timeout=15.0)
                    yield notification.to_sse_data()
                except queue.Empty:
                    # Tarayıcı veya proxy zaman aşımını engellemek için keepalive yorumu
                    yield ": keepalive\n\n"
        finally:
            broker.unsubscribe(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
