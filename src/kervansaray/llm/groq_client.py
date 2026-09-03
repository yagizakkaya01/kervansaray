"""Groq (Llama 3.3) istemcisi.

CILEKAI `infra/llm/groq_client.py`'den tasindi (PROJECT_BRIEF S13).
Ortak arayuz:  generate(text, system_instruction=None) -> dict
"""
from __future__ import annotations

import logging

from groq import Groq

from kervansaray.config import settings

log = logging.getLogger(__name__)

PROVIDER = "groq"


def available() -> bool:
    return bool(settings.GROQ_API_KEY)


def generate(text: str, system_instruction: str | None = None) -> dict:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY eksik")

    client = Groq(api_key=settings.GROQ_API_KEY, timeout=settings.LLM_REQUEST_TIMEOUT)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": text})

    completion = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_completion_tokens=settings.LLM_MAX_TOKENS,
        stream=False,
    )
    return {"response": completion.choices[0].message.content, "provider": PROVIDER}
