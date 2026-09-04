"""Flask uygulama fabrikasi.

CILEKAI `main.py` app-factory deseninden tasindi, RAG bootstrap'i olmadan.
Ingest API + saglik + Prometheus. Tool katmani / panel sonraki fazlar.
"""
from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text

from kervansaray.db import session_scope
from kervansaray.logging import setup_logging
from kervansaray.observability import init_metrics

from .routes_events import bp as events_bp


def create_app() -> Flask:
    setup_logging()
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})  # Faz 8c'de kisitlanacak

    init_metrics(app)
    app.register_blueprint(events_bp)

    @app.get("/healthz")
    def healthz():
        try:
            with session_scope() as db:
                db.execute(text("SELECT 1"))
            return jsonify({"ok": True}), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc)}), 503

    return app

