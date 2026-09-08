"""LLM istemci katmanı.

Aktif sağlayıcı: Gemini 2.0 Flash (`gemini_client`).
OpenAI/Groq Function Calling istemcileri ilgili API anahtarları tanımlandığında
`OPENAI_TOOLS` şeması üzerinden bağlanacaktır.
"""
from __future__ import annotations

from . import gemini_client

__all__ = ["gemini_client"]
