"""LLM saglayici fallback zinciri.

CILEKAI'da fallback ad hoc dagilmisti (rag_pipeline.py icinde groq ->
gemini). Burada tek noktaya toplandi (PROJECT_BRIEF S13 - "provider
fallback chain"): `settings.provider_order` sirasiyla saglayicilar
denenir, ilk basarili cevap doner.

    from kervansaray.llm import generate_with_fallback

    out = generate_with_fallback("Merhaba", system_instruction="...")
    # -> {"response": "...", "provider": "groq", "fell_back": False}
"""
from __future__ import annotations

import logging
from time import perf_counter

from kervansaray.config import settings
from kervansaray.observability import LLM_LATENCY, LLM_REQUESTS

from . import gemini_client, groq_client, openai_client

log = logging.getLogger(__name__)

_CLIENTS = {
    groq_client.PROVIDER: groq_client,
    gemini_client.PROVIDER: gemini_client,
    openai_client.PROVIDER: openai_client,
}


class AllProvidersFailed(RuntimeError):
    """Zincirdeki her saglayici hata verdi."""


def generate_with_fallback(text: str, system_instruction: str | None = None) -> dict:
    order = [p for p in settings.provider_order if p in _CLIENTS]
    if not order:
        raise AllProvidersFailed("Yapilandirilmis saglayici yok (LLM_PROVIDER_ORDER)")

    errors: list[str] = []
    for idx, name in enumerate(order):
        client = _CLIENTS[name]
        if not client.available():
            errors.append(f"{name}: anahtar yok")
            continue
        t0 = perf_counter()
        try:
            out = client.generate(text, system_instruction=system_instruction)
            LLM_LATENCY.labels(name).observe(perf_counter() - t0)
            LLM_REQUESTS.labels(name, "ok").inc()
            out["fell_back"] = idx > 0
            return out
        except Exception as exc:  # noqa: BLE001 - siradaki saglayiciya gec
            LLM_LATENCY.labels(name).observe(perf_counter() - t0)
            LLM_REQUESTS.labels(name, "error").inc()
            log.warning("LLM saglayici '%s' basarisiz: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise AllProvidersFailed("; ".join(errors))
