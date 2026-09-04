"""Sentetik veri uretici CLI (ROADMAP Faz 2).

Ornekler:
    # populasyonu DB'ye yaz + tum olaylari ingest API'sine gonder
    python scripts/synth.py --reset --seed-db --post http://localhost:8000

    # sadece dosyaya uret (API yok)
    python scripts/synth.py --out data/events.jsonl

    # sadece ozet (dry-run)
    python scripts/synth.py --days 30 --vehicles 80
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from kervansaray.synth import generate
from kervansaray.synth.loader import dump_manifest, post_stream, write_jsonl
from kervansaray.synth.scenario import DEFAULT_DAYS, DEFAULT_SIZE


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kervansaray sentetik olay uretici")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--start", type=date.fromisoformat, default=None,
                   help="YYYY-MM-DD (varsayilan: bugun - days)")
    p.add_argument("--vehicles", type=int, default=DEFAULT_SIZE)
    p.add_argument("--out", metavar="PATH", help="olaylari JSONL dosyasina yaz")
    p.add_argument("--post", metavar="URL", help="olaylari ingest API'sine gonder ( or. http://localhost:8000)")
    p.add_argument("--seed-db", action="store_true", help="populasyonu DB'ye yaz")
    p.add_argument("--reset", action="store_true", help="once tum tablolari TRUNCATE et")
    p.add_argument("--manifest", metavar="PATH", default="synth_manifest.json")
    return p.parse_args(argv)


def _reset_db() -> None:
    from sqlalchemy import text

    from kervansaray.db import session_scope

    tables = "sessions, events, registrations, vehicles, persons, notes, daily_summaries"
    with session_scope() as db:
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    print(f"reset: {tables} temizlendi")


def _seed_population(pop) -> None:
    from kervansaray.db import session_scope
    from kervansaray.synth.population import is_empty, persist

    with session_scope() as db:
        if not is_empty(db):
            print("HATA: vehicles tablosu bos degil. --reset kullanin.", file=sys.stderr)
            sys.exit(2)
        persist(db, pop)
    print(f"seed-db: {len(pop.vehicles)} arac yazildi")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    sc = generate(seed=args.seed, start=args.start, days=args.days, size=args.vehicles)
    c = sc.manifest["counts"]
    print(
        f"uretildi: seed={args.seed} days={args.days} vehicles={sc.manifest['population_size']} "
        f"| {c['events_delivered']} olay ({c['events_unique']} tekil), "
        f"{c['entries']} giris / {c['exits']} cikis"
    )

    if args.reset:
        _reset_db()
    if args.seed_db:
        _seed_population(sc.population)

    if args.out:
        n = write_jsonl(args.out, sc.payloads())
        print(f"out: {n} olay -> {args.out}")

    if args.post:
        def _progress(i: int, st) -> None:
            print(f"  ... {i}  created={st.created} dup={st.duplicate} fail={st.failed}")

        stats = post_stream(args.post, sc.payloads(), on_progress=_progress)
        print(
            f"post: created={stats.created} duplicate={stats.duplicate} failed={stats.failed}"
        )
        for e in stats.errors:
            print(f"  ! {e}", file=sys.stderr)
        if stats.failed:
            return 1

    dump_manifest(args.manifest, sc.manifest)
    print(f"manifest -> {args.manifest}  (uretim: {datetime.now().isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
