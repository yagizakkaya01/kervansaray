"""Deterministik plaka uretimi (sentetik veri).

Kural (PROJECT_BRIEF S8 - "Dummy plate convention"):
  - Kutle veri GERCEK il kodlariyla (01-81) uretilir ki gercek dogrulama
    yolundan gecsin.
  - 82-99 il kodlari Turkiye'de yok; yalnizca "bu kesinlikle test verisi"
    demek ve gecersiz-il ret yolunu denemek icin ayrilir.

Uretilen tum (harf,rakam) kombinasyonlari text.plates._VALID_SHAPES ile
uyumludur, boylece populasyon plakalari `parse().valid == True` olur.
"""
from __future__ import annotations

from random import Random

# Turk plakalarinda kullanilan harfler (Q/W/X ve Turkce'ye ozgu harfler yok).
PLATE_LETTERS = "ABCDEFGHIJKLMNOPRSTUVYZ"

# (harf, rakam) - text.plates._VALID_SHAPES ile ayni tutulmali.
_SHAPES = ((1, 4), (2, 3), (2, 4), (3, 2), (3, 3))


def _letters(rng: Random, n: int) -> str:
    return "".join(rng.choice(PLATE_LETTERS) for _ in range(n))


def _digits(rng: Random, n: int) -> str:
    # Bas sifira izin var (gercek plakalarda gorulur: 34 A 0034).
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


def random_plate(rng: Random, *, province: int | None = None, synthetic: bool = False) -> str:
    """Kanonik formda ('34ABC123') tek bir plaka uretir.

    synthetic=True -> il kodu 82-99 (kesin sentetik, gecersiz il).
    """
    if province is None:
        province = rng.randint(82, 99) if synthetic else rng.randint(1, 81)
    n_letters, n_digits = rng.choice(_SHAPES)
    return f"{province:02d}{_letters(rng, n_letters)}{_digits(rng, n_digits)}"


def unique_plates(
    rng: Random, count: int, *, synthetic_ratio: float = 0.0
) -> list[str]:
    """`count` adet benzersiz plaka. synthetic_ratio kadari 82-99 il kodlu."""
    n_synth = round(count * synthetic_ratio)
    out: set[str] = set()
    while len(out) < count:
        want_synth = len(out) < n_synth
        out.add(random_plate(rng, synthetic=want_synth))
    return sorted(out)


def corrupt_one_char(rng: Random, plate: str) -> str:
    """Plakada tek karakteri komsu bir karakterle degistirir (OCR hatasi taklidi).

    Rakam <-> rakam, harf <-> harf; il kodu (ilk 2 hane) korunur ki hata
    ayni il havuzunda kalsin (S4.1 gramer kisiti bunu zaten saglar).
    """
    idx = rng.randrange(2, len(plate))
    ch = plate[idx]
    if ch.isdigit():
        repl = str((int(ch) + rng.choice((-1, 1))) % 10)
    else:
        pos = PLATE_LETTERS.index(ch) if ch in PLATE_LETTERS else 0
        repl = PLATE_LETTERS[(pos + rng.choice((-1, 1))) % len(PLATE_LETTERS)]
    return plate[:idx] + repl + plate[idx + 1 :]
