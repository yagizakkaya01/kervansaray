"""Altin set eval harness - PLACEHOLDER (ROADMAP Faz 3).

Faz 3'te bu script ~50 soruluk altin seti sentetik DB'ye karsi calistirip
tek bir dogruluk sayisi raporlayacak (PROJECT_BRIEF S9). Su an sadece CI
job iskeletini yesil tutar.
"""
from __future__ import annotations

import sys
from pathlib import Path

GOLD = Path(__file__).resolve().parent.parent / "tests" / "gold_set.jsonl"


def main() -> int:
    if not GOLD.exists():
        print("eval: gold set henuz yok (ROADMAP Faz 3). Iskelet job gecti.")
        return 0
    print("eval: gold set bulundu ama runner implemente edilmedi.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
