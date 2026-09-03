"""Google Gemini istemcisi.

CILEKAI `infra/llm/gemini_client.py`'den tasindi (PROJECT_BRIEF S13).
CILEKAI'daki dosyaya-yazan debug log kancalari (_dlog) cikarildi;
fork-safe `requests.Session` + sinirli retry deseni korundu.

Ortak arayuz:  generate(text, system_instruction=None) -> dict
"""
from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter, Retry

from kervansaray.config import settings

log = logging.getLogger(__name__)

PROVIDER = "gemini"
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def available() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _session() -> requests.Session:
    """Her cagride taze Session (fork-safe)."""
    s = requests.Session()
    s.mount(
        "https://",
        HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["POST"]),
        )),
    )
    return s


def generate(text: str, system_instruction: str | None = None) -> dict:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY eksik")

    url = f"{_BASE}/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    body: dict = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": settings.LLM_TEMPERATURE,
            "maxOutputTokens": settings.LLM_MAX_TOKENS,
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    r = _session().post(url, json=body, timeout=settings.LLM_REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")

    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "bilinmiyor")
        raise RuntimeError(f"Gemini bos cevap (sebep: {reason})")

    final_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return {"response": final_text, "provider": PROVIDER}
