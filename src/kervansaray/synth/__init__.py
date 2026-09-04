"""Sentetik olay uretici (ROADMAP Faz 2 / PROJECT_BRIEF S8).

Deterministik: ayni tohum + parametreler ayni populasyon ve olay akisini
verir. Cikti ingest API'sinden yuklenir (kendi API'ni dogfood et).

    from kervansaray.synth import generate
    sc = generate(seed=42, days=90, size=200)
    sc.payloads()   # list[EventV1] - POST /events'e gonderilecek
    sc.manifest     # ground-truth ozeti (Faz 3 altin seti buna dayanir)
"""
from __future__ import annotations

from .dirt import DirtConfig
from .scenario import TR, Scenario, generate

__all__ = ["generate", "Scenario", "DirtConfig", "TR"]
