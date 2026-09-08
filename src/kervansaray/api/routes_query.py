"""Doğal dil sorgu ucu (POST /api/query).

Kullanıcı sorusunu alır, LLM ve SQL araçları üzerinden çalıştırıp
üçlü çıktıyı (anlatı, tool çağrısı, veri tablosu) döner.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from kervansaray.db import session_scope
from kervansaray.query_pipeline import run_query

bp = Blueprint("query", __name__, url_prefix="/api")


@bp.post("/query")
def post_query():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Geçersiz JSON gövdesi."}), 400

    query_text = (body.get("query") or "").strip()
    if not query_text:
        return jsonify({"error": "Sorgu metni ('query') boş olamaz."}), 400

    as_of = None
    as_of_raw = body.get("as_of")
    if as_of_raw:
        try:
            as_of = datetime.fromisoformat(as_of_raw)
        except ValueError:
            return jsonify({"error": f"Geçersiz 'as_of' ISO formatı: {as_of_raw}"}), 400

    use_cache = bool(body.get("use_cache", True))

    with session_scope() as db:
        res = run_query(query_text, db, as_of=as_of, use_cache=use_cache)

    return jsonify(res), 200
