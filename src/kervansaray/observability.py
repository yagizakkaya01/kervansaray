"""Prometheus metrikleri + Flask entegrasyonu.

CILEKAI `main.py` icindeki inline Prometheus kurulumundan tasindi
(PROJECT_BRIEF S13). CILEKAI'nin RAG'e ozel metrikleri (rag_retrieval_*,
rag_refresh_*, rag_index_size) yerine bu projenin alanina uygun metrikler
tanimlandi: olay ingest, tool cagrilari, LLM saglayici sonuclari, kural
motoru bildirimleri, plaka eslestirme.

Kullanim (uygulama fabrikasi icinde):

    from kervansaray.observability import init_metrics
    init_metrics(app)
"""
from __future__ import annotations

from time import perf_counter

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .config import settings

# --- HTTP ---
REQ_COUNT = Counter("http_requests_total", "HTTP istek sayisi", ["endpoint", "method", "status"])
REQ_LATENCY = Histogram(
    "http_request_latency_seconds", "HTTP istek gecikmesi", buckets=(0.01, 0.3, 1, 3, 10)
)

# --- Alan metrikleri ---
EVENTS_INGESTED = Counter(
    "events_ingested_total", "Islenen arac hareketi olaylari", ["direction", "match_status"]
)
EVENTS_DUPLICATE = Counter(
    "events_duplicate_total", "event_id idempotency ile atlanan tekrar olaylar"
)
TOOL_CALLS = Counter("tool_calls_total", "Tool cagrilari", ["tool", "outcome"])
TOOL_LATENCY = Histogram(
    "tool_call_latency_seconds", "Tool cagri gecikmesi", ["tool"],
    buckets=(0.005, 0.01, 0.03, 0.1, 0.3, 1, 3),
)
LLM_REQUESTS = Counter("llm_requests_total", "LLM saglayici cagrilari", ["provider", "outcome"])
LLM_LATENCY = Histogram(
    "llm_request_latency_seconds", "LLM cagri gecikmesi", ["provider"],
    buckets=(0.1, 0.3, 1, 3, 10, 30),
)
NOTIFICATIONS_FIRED = Counter(
    "notifications_fired_total", "Kural motorunun tetikledigi bildirimler", ["rule"]
)
PLATE_MATCH = Counter(
    "plate_match_total", "Plaka eslestirme sonuclari", ["status"]  # exact|fuzzy|unmatched|pending
)
VEHICLES_ONSITE = Gauge("vehicles_onsite", "Su an sahada oldugu bilinen arac sayisi")


def init_metrics(app) -> None:
    """Flask uygulamasina before/after request kancalarini ve /metrics ucunu ekler."""

    @app.before_request
    def _start_timer():  # noqa: WPS430
        if settings.METRICS_ENABLED:
            from flask import request

            request._start_time = perf_counter()

    @app.after_request
    def _observe(resp):  # noqa: WPS430
        if settings.METRICS_ENABLED:
            try:
                from flask import request

                st = getattr(request, "_start_time", None)
                if st is not None:
                    REQ_LATENCY.observe(perf_counter() - st)
                REQ_COUNT.labels(
                    request.endpoint or "unknown", request.method, str(resp.status_code)
                ).inc()
            except Exception:  # metrik hatasi istegi bozmasin
                pass
        return resp

    @app.route(settings.METRICS_PATH)
    def _metrics():  # noqa: WPS430
        if not settings.METRICS_ENABLED:
            return {"error": "disabled"}, 404
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
