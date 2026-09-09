"""Doğal dil sorgu ucu (POST /api/query).

Kullanıcı sorusunu alır, LLM ve SQL araçları üzerinden çalıştırıp
üçlü çıktıyı (anlatı, tool çağrısı, veri tablosu) döner.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from kervansaray.api.rate_limit import limiter
from kervansaray.db import session_scope
from kervansaray.query_pipeline import query_cache, run_query
from kervansaray.text.turkish import to_ascii

bp = Blueprint("query", __name__, url_prefix="/api")


MAX_QUERY_LENGTH = 500


@bp.post("/query")
def post_query():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Geçersiz JSON gövdesi."}), 400

    query_text = (body.get("query") or "").strip()
    if not query_text:
        return jsonify({"error": "Sorgu metni ('query') boş olamaz."}), 400
    if len(query_text) > MAX_QUERY_LENGTH:
        return jsonify({
            "error": (
                f"Sorgu metni çok uzun (en fazla {MAX_QUERY_LENGTH} "
                f"karakter, gelen: {len(query_text)})."
            )
        }), 400

    as_of = None
    as_of_raw = body.get("as_of")
    if as_of_raw:
        try:
            as_of = datetime.fromisoformat(as_of_raw)
        except ValueError:
            return jsonify({"error": f"Geçersiz 'as_of' ISO formatı: {as_of_raw}"}), 400

    use_cache = bool(body.get("use_cache", True))

    # Önbellekte bulunan (hazır çip/senaryo) sorgular kota harcamaz (0ms, $0 maliyet).
    cache_ref = as_of.isoformat() if as_of else "now"
    cache_key = f"{to_ascii(query_text.lower())}:{cache_ref}"
    is_cached = use_cache and (query_cache.get(cache_key) is not None)

    if not is_cached:
        client_ip = request.remote_addr or "127.0.0.1"
        allowed, err_msg = limiter.is_allowed(client_ip)
        if not allowed:
            return jsonify({"error": err_msg}), 429

    with session_scope() as db:
        res = run_query(query_text, db, as_of=as_of, use_cache=use_cache)

    return jsonify(res), 200


@bp.post("/rate-limit/reset")
def reset_rate_limit():
    """Test ve demo sırasında soru limitini anında sıfırlar."""
    limiter.clear()
    return jsonify({"ok": True, "message": "Soru kotası ve hız limitleri başarıyla sıfırlandı."}), 200

