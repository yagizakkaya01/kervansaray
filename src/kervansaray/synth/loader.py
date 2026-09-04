"""Sentetik akisi ingest API'sine yukler ya da dosyaya yazar.

PROJECT_BRIEF S8: uretici ciktisini KENDI ingest API'sinden yukler
(dogfooding). Populasyon (arac/kisi/kayit) referans veridir, API'si yok -
DB'ye dogrudan yazilir (population.persist).
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import requests

from kervansaray.events import EventV1


@dataclass
class PostStats:
    created: int = 0
    duplicate: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.duplicate + self.failed


def write_jsonl(path: str | Path, payloads: Iterable[EventV1]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for ev in payloads:
            f.write(ev.model_dump_json() + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> list[EventV1]:
    with Path(path).open(encoding="utf-8") as f:
        return [EventV1.model_validate_json(line) for line in f if line.strip()]


def post_stream(
    base_url: str,
    payloads: Iterable[EventV1],
    *,
    timeout: float = 10.0,
    on_progress: Callable[[int, PostStats], None] | None = None,
    progress_every: int = 250,
) -> PostStats:
    url = base_url.rstrip("/") + "/events"
    stats = PostStats()
    session = requests.Session()
    for i, ev in enumerate(payloads, start=1):
        try:
            resp = session.post(url, data=ev.model_dump_json(),
                                headers={"Content-Type": "application/json"}, timeout=timeout)
            if resp.status_code == 201:
                stats.created += 1
            elif resp.status_code == 200:
                stats.duplicate += 1
            else:
                stats.failed += 1
                if len(stats.errors) < 10:
                    stats.errors.append(f"{resp.status_code}: {resp.text[:180]}")
        except requests.RequestException as exc:
            stats.failed += 1
            if len(stats.errors) < 10:
                stats.errors.append(str(exc))
        if on_progress and i % progress_every == 0:
            on_progress(i, stats)
    return stats


def dump_manifest(path: str | Path, manifest: dict) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
