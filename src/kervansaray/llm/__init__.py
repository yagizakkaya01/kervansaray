"""LLM istemci katmanı.

Desteklenen sağlayıcılar:
- NVIDIA NIM (`nvidia_client`, varsayılan model: `nvidia/nemotron-3.5-lightning-30b-a3b`)
- Google Gemini Flash (`gemini_client`, varsayılan model: `gemini-3.8-flash`)
"""
from __future__ import annotations

from typing import Any

from kervansaray.config import settings

from . import gemini_client, nvidia_client

CLIENTS: dict[str, Any] = {
    "nvidia": nvidia_client,
    "gemini": gemini_client,
}


def get_available_clients() -> list[Any]:
    """`settings.provider_order` sırasına göre kullanılabilir LLM istemcilerini döner."""
    order = settings.provider_order
    available: list[Any] = []
    for name in order:
        client = CLIENTS.get(name)
        if client and client.available():
            available.append(client)
    return available


__all__ = ["gemini_client", "nvidia_client", "get_available_clients"]
