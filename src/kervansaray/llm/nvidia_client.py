"""NVIDIA NIM istemcisi (Nemotron 3.5 Lightning 30B ve OpenAI uyumlu modeller).

Ponytail prensibi: Harici SDK yüklemeden standart `requests` ile OpenAI formatında
Tool Calling (Function Calling) ve sohbet tamamlama sağlar.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter, Retry

from kervansaray.config import settings

log = logging.getLogger(__name__)

PROVIDER = "nvidia"


def available() -> bool:
    """NVIDIA API anahtarının tanımlı olup olmadığını doğrular."""
    return bool(settings.NVIDIA_API_KEY)


def _session() -> requests.Session:
    """Her çağrıda taze Session (fork-safe) ve yeniden deneme adaptörü."""
    s = requests.Session()
    s.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset(["POST"]),
            )
        ),
    )
    return s


def _format_tools_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gelen fonksiyon şemalarını OpenAI tool formatına dönüştürür."""
    formatted: list[dict[str, Any]] = []
    for t in tools:
        if "type" in t and "function" in t:
            formatted.append(t)
        elif "function_declarations" in t:
            for fd in t["function_declarations"]:
                formatted.append({"type": "function", "function": fd})
        elif "name" in t:
            formatted.append({"type": "function", "function": t})
    return formatted


def generate(
    text: str,
    system_instruction: str | None = None,
    *,
    tools: list[dict[str, Any]] | None = None,
    few_shots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """NVIDIA NIM modeline istek gönderir; tool_call veya metin yanıtı döner."""
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY eksik")

    url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    full_instruction = system_instruction or ""
    if not tools and few_shots and "ÖRNEKLER:" not in full_instruction:
        lines = []
        for ex in few_shots:
            if "tool_call" in ex:
                tc = ex["tool_call"]
                lines.append(f'- Soru: "{ex["question"]}" -> Araç: {tc["name"]}({tc["args"]})')
            else:
                lines.append(f'- Soru: "{ex["question"]}" -> Yanıt: {ex.get("response")}')
        full_instruction += "\n\nÖRNEKLER:\n" + "\n".join(lines)

    messages: list[dict[str, Any]] = []
    if full_instruction:
        messages.append({"role": "system", "content": full_instruction})
    messages.append({"role": "user", "content": text})

    body: dict[str, Any] = {
        "model": settings.NVIDIA_MODEL,
        "messages": messages,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }

    if tools:
        formatted_tools = _format_tools_openai(tools)
        if formatted_tools:
            body["tools"] = formatted_tools
            body["tool_choice"] = "auto"

    r = _session().post(url, headers=headers, json=body, timeout=settings.LLM_REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"NVIDIA {r.status_code}: {r.text[:250]}")

    data = r.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("NVIDIA boş yanıt döndü")

    msg = choices[0].get("message", {})
    tool_calls = msg.get("tool_calls", [])

    if tool_calls:
        first_tc = tool_calls[0].get("function", {})
        fn_name = first_tc.get("name")
        raw_args = first_tc.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                fn_args = json.loads(raw_args)
            except json.JSONDecodeError:
                fn_args = {}
        elif isinstance(raw_args, dict):
            fn_args = raw_args
        else:
            fn_args = {}

        return {
            "provider": PROVIDER,
            "function_call": {
                "name": fn_name,
                "args": fn_args,
            },
            "raw": data,
        }

    content = msg.get("content") or ""
    return {
        "provider": PROVIDER,
        "response": content,
        "raw": data,
    }
