"""LLM istemci katmanı.

Aktif sağlayıcı: Google Gemini Flash (`gemini_client`, varsayılan model: `gemini-3.8-flash`).
OpenAI/Groq Function Calling istemcileri ilgili API anahtarları tanımlandığında
`OPENAI_TOOLS` şeması üzerinden bağlanacaktır.
"""
from __future__ import annotations

from . import gemini_client

__all__ = ["gemini_client"]
