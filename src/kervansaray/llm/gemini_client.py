"""Google Gemini istemcisi (Function Calling ve Tool desteği ile).

CILEKAI `infra/llm/gemini_client.py`'den tasindi (PROJECT_BRIEF S13).
Fonksiyon cagirma (Function Calling) ve few-shot destegi eklendi.
"""
from __future__ import annotations

import logging
from typing import Any

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


def generate(
    text: str,
    system_instruction: str | None = None,
    *,
    tools: list[dict[str, Any]] | None = None,
    few_shots: list[dict[str, Any]] | None = None,
) -> dict:
    """Gemini modeline metin gonderir; metin veya function_call yaniti doner."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY eksik")

    url = f"{_BASE}/{settings.GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY}

    full_instruction = system_instruction or ""
    if few_shots and "ÖRNEKLER:" not in full_instruction:
        lines = []
        for ex in few_shots:
            if "tool_call" in ex:
                tc = ex["tool_call"]
                lines.append(f'- Soru: "{ex["question"]}" -> Araç: {tc["name"]}({tc["args"]})')
            else:
                lines.append(f'- Soru: "{ex["question"]}" -> Yanıt: {ex.get("response")}')
        full_instruction += "\n\nÖRNEKLER:\n" + "\n".join(lines)

    contents: list[dict[str, Any]] = [{"role": "user", "parts": [{"text": text}]}]

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": settings.LLM_TEMPERATURE,
            "maxOutputTokens": settings.LLM_MAX_TOKENS,
        },
    }

    if full_instruction:
        body["systemInstruction"] = {"parts": [{"text": full_instruction}]}

    if tools:
        if "function_declarations" not in tools[0]:
            body["tools"] = [{"function_declarations": tools}]
        else:
            body["tools"] = tools

    r = _session().post(url, headers=headers, json=body, timeout=settings.LLM_REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:250]}")

    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "bilinmiyor")
        raise RuntimeError(f"Gemini bos cevap (sebep: {reason})")

    parts = candidates[0].get("content", {}).get("parts", [{}])
    first_part = parts[0] if parts else {}

    if "functionCall" in first_part:
        fc = first_part["functionCall"]
        return {
            "function_call": {
                "name": fc.get("name"),
                "args": fc.get("args", {}),
            },
            "response": None,
            "provider": PROVIDER,
        }

    final_text = first_part.get("text", "")
    return {"response": final_text, "function_call": None, "provider": PROVIDER}
