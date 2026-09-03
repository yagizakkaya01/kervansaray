"""OpenAI (GPT-4o) istemcisi.

CILEKAI `infra/llm/openai_client.py`'den tasindi (PROJECT_BRIEF S13).
CILEKAI'daki "yerel model adini gpt-4o'ya zorla" mantigi cikarildi -
bu projede yerel model yok (PROJECT_BRIEF S10).

Ortak arayuz:  generate(text, system_instruction=None) -> dict
"""
from __future__ import annotations

import logging

from openai import OpenAI

from kervansaray.config import settings

log = logging.getLogger(__name__)

PROVIDER = "openai"


def available() -> bool:
    return bool(settings.OPENAI_API_KEY)


def generate(text: str, system_instruction: str | None = None) -> dict:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY eksik")

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.LLM_REQUEST_TIMEOUT)
    messages = [
        {"role": "system", "content": system_instruction or "Sen yardimci bir asistansin."},
        {"role": "user", "content": text},
    ]
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    return {"response": response.choices[0].message.content.strip(), "provider": PROVIDER}
