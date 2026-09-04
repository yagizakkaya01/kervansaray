"""Deterministik, akis-bazli rastgelelik.

Tek bir `Random(seed)` tum ureticiyi beslerse, herhangi bir yere fazladan
bir `rng` cagrisi eklemek sonraki her seyi kaydirir ve altin set (Faz 3)
bozulur. Bunun yerine isimli alt-akislar kullanilir: `for_stream("rhythm")`
her zaman ayni tohumdan turer, dolayisiyla akislar birbirinden bagimsizdir.
"""
from __future__ import annotations

import hashlib
from random import Random


class SynthRandom:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def for_stream(self, name: str) -> Random:
        h = hashlib.sha256(f"{self.seed}:{name}".encode()).digest()
        return Random(int.from_bytes(h[:8], "big"))
