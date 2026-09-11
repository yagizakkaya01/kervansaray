"""Konteynerler-arasi ic uclar - Caddyfile'a EKLENMEZ, internetten erisilemez.

Sadece `portfolio_default` Docker agi uzerinden portfolio'nun `web` servisi
tarafindan cagrilir (admin dashboard -> GET /api/admin/query-log -> burada).
Guven siniri Caddy'nin bilincli allowlist deseniyle ayni: bu yol handle
blogunda yoksa disaridan asla gorunmez.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from kervansaray.db import session_scope
from kervansaray.query_log import list_recent

bp = Blueprint("internal", __name__, url_prefix="/api/internal")


@bp.get("/query-log")
def get_query_log():
    limit = request.args.get("limit", default=200, type=int) or 200
    with session_scope() as db:
        rows = list_recent(db, limit=limit)
        return jsonify({
            "entries": [
                {"query_text": r.query_text, "ts": r.created_at.isoformat()}
                for r in rows
            ]
        }), 200
