"""Yapilandirma yonetimi.

CILEKAI `core/config.py` deseninden tasindi (PROJECT_BRIEF S13):
pydantic-settings `BaseSettings`, tum degerler `.env`'den, sinif icinde
guvenli varsayilanlar. CILEKAI'daki RAG / embedding / chunking / rerank
ayarlari tasinmadi - bu projede retrieval yigini yok (PROJECT_BRIEF S12).
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Sunucu ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # --- Veritabani ---
    # Postgres + pgvector; sadece localhost'a bagli (PROJECT_BRIEF S10).
    DATABASE_URL: str = "postgresql://kervansaray:kervansaray@localhost:5432/kervansaray"

    # --- LLM saglayicilari (bulut API) ---
    # Fallback sirasi: ilk basarili saglayici kazanir (bkz. llm/__init__.py).
    LLM_PROVIDER_ORDER: str = "groq,gemini,openai"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1024
    LLM_REQUEST_TIMEOUT: float = 60.0

    # --- Loglama ---
    LOG_LEVEL: str = "INFO"
    LOG_TO_FILE: bool = True
    LOG_FILE: str = "logs/app.log"

    # --- Gozlemlenebilirlik ---
    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"

    @property
    def provider_order(self) -> list[str]:
        return [p.strip().lower() for p in self.LLM_PROVIDER_ORDER.split(",") if p.strip()]


settings = Settings()
