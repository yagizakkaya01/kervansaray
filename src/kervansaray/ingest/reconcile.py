"""Plaka mutabakati - gozlemlenen plakayi bilinen bir araca baglamak.

PROJECT_BRIEF S3.8: bu bir arama degil, anahtar aramasidir.
    1. Kanoniklestir (text.plates.canonicalize)
    2. Birebir lookup:  SELECT * FROM vehicles WHERE plate = ?   -> exact
    3. Birebir yoksa bounded fuzzy (text.fuzzy.best_match):
       edit distance 1'lik eslesme ASLA otomatik kabul edilmez -> pending
       (aday vehicle + skor saklanir, insan onayina kuyruklanir)
    4. Hicbiri -> unmatched
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from kervansaray.db.models import MatchStatus, Vehicle
from kervansaray.text.fuzzy import best_match
from kervansaray.text.plates import canonicalize

# Bounded fuzzy esigi. Altinda hicbir aday onerilmez.
FUZZY_MIN_SCORE = 88.0


@dataclass(frozen=True)
class ReconcileResult:
    canonical_plate: str
    status: MatchStatus
    vehicle_id: int | None = None
    candidate_vehicle_id: int | None = None
    score: float | None = None


def _known_plates(db: Session, province_prefix: str | None = None) -> list[str]:
    stmt = select(Vehicle.plate)
    if province_prefix:
        stmt = stmt.where(Vehicle.plate.like(f"{province_prefix}%"))
    return list(db.scalars(stmt))


def reconcile_plate(db: Session, raw_plate: str) -> ReconcileResult:
    canon = canonicalize(raw_plate)

    # 2. Birebir anahtar aramasi.
    exact = db.scalar(select(Vehicle).where(Vehicle.plate == canon))
    if exact is not None:
        return ReconcileResult(canon, MatchStatus.exact, vehicle_id=exact.id, score=100.0)

    # 3. Bounded fuzzy. Il kodu (ilk 2 hane) ile aday havuzunu daralt - plaka
    #    yanlis okumalari nadiren il kodunu degistirir (S4.1 gramer kisiti).
    prefix = canon[:2] if len(canon) >= 2 and canon[:2].isdigit() else None
    candidates = _known_plates(db, prefix)
    match = best_match(canon, candidates, min_score=FUZZY_MIN_SCORE)
    if match is not None:
        cand = db.scalar(select(Vehicle).where(Vehicle.plate == match.value))
        # S3.8: her fuzzy aday insan onayina gider (auto-accept yok).
        return ReconcileResult(
            canon,
            MatchStatus.pending,
            candidate_vehicle_id=cand.id if cand else None,
            score=match.score,
        )

    # 4. Eslesme yok.
    return ReconcileResult(canon, MatchStatus.unmatched)
