"""Sentetik olay uretici (ROADMAP Faz 2 / PROJECT_BRIEF S8).

Deterministik: ayni tohum + parametreler ayni populasyon ve olay akisini
verir. Cikti ingest API'sinden yuklenir (kendi API'ni dogfood et).

    from kervansaray.synth import generate
    sc = generate(seed=42, days=90, size=200)
    sc.payloads()   # list[EventV1] - POST /events'e gonderilecek
    sc.manifest     # ground-truth ozeti (Faz 3 altin seti buna dayanir)
"""
from __future__ import annotations

import sys

# Geriye donuk tam uyumluluk icin alt-modul alias'lari
from . import dirt, generator, population
from .dirt import DirtConfig, inject_anomalies
from .dirt import inject as inject_dirt
from .generator import (
    DEFAULT_DAYS,
    DEFAULT_SIZE,
    DEVICE_ID,
    MODEL_VERSION,
    PLATE_LETTERS,
    TR,
    GenEvent,
    PostStats,
    Scenario,
    SynthRandom,
    build_events,
    corrupt_one_char,
    dump_manifest,
    generate,
    post_stream,
    random_plate,
    read_jsonl,
    unique_plates,
    write_jsonl,
)
from .notes import OPERATIONAL_NOTES, get_synthetic_notes
from .population import (
    GUEST_SHARE,
    N_SYNTHETIC,
    STAFF_SHARE,
    VENDOR_SHARE,
    Population,
    VehicleSpec,
    Visit,
    build_population,
    build_visits,
    is_empty,
    persist,
)

loader = generator
scenario = generator
events = generator
plates = generator
rng = generator
rhythm = population
anomalies = dirt

sys.modules[f"{__name__}.loader"] = generator
sys.modules[f"{__name__}.scenario"] = generator
sys.modules[f"{__name__}.events"] = generator
sys.modules[f"{__name__}.plates"] = generator
sys.modules[f"{__name__}.rng"] = generator
sys.modules[f"{__name__}.rhythm"] = population
sys.modules[f"{__name__}.anomalies"] = dirt

__all__ = [
    "DEFAULT_DAYS",
    "DEFAULT_SIZE",
    "DEVICE_ID",
    "DirtConfig",
    "GUEST_SHARE",
    "GenEvent",
    "MODEL_VERSION",
    "N_SYNTHETIC",
    "OPERATIONAL_NOTES",
    "get_synthetic_notes",
    "PLATE_LETTERS",
    "Population",
    "PostStats",
    "STAFF_SHARE",
    "Scenario",
    "SynthRandom",
    "TR",
    "VENDOR_SHARE",
    "VehicleSpec",
    "Visit",
    "anomalies",
    "build_events",
    "build_population",
    "build_visits",
    "corrupt_one_char",
    "dirt",
    "dump_manifest",
    "events",
    "generate",
    "generator",
    "inject_anomalies",
    "inject_dirt",
    "is_empty",
    "loader",
    "persist",
    "plates",
    "population",
    "post_stream",
    "random_plate",
    "read_jsonl",
    "rhythm",
    "rng",
    "scenario",
    "unique_plates",
    "write_jsonl",
]
