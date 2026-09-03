"""Sinirli (bounded) bulanik eslestirme.

CILEKAI `core/faq_manager.py` rapidfuzz kullanimindan tasindi
(PROJECT_BRIEF S13 - "fuzzy matching utilities").

PROJECT_BRIEF S3.8 kurali burada kodlanmistir: bir OCR plakasi bilinen
bir plakaya TAM eslemiyorsa, edit distance 1'lik eslesme ASLA otomatik
kabul edilmez - `needs_confirmation=True` ile isaretlenip insan onayina
kuyruklanır.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein


@dataclass(frozen=True)
class FuzzyMatch:
    value: str
    score: float           # 0-100
    edit_distance: int
    needs_confirmation: bool


def best_match(
    query: str,
    candidates: list[str],
    *,
    min_score: float = 85.0,
    auto_accept_score: float = 100.0,
) -> FuzzyMatch | None:
    """En iyi adayi dondurur; yoksa None.

    - Tam eslesme (score == 100, edit_distance == 0) -> needs_confirmation=False
    - `min_score` uzeri ama tam degil -> needs_confirmation=True (S3.8)
    - `min_score` alti -> None
    """
    if not candidates:
        return None

    hit = process.extractOne(query, candidates, scorer=fuzz.ratio)
    if hit is None:
        return None

    value, score, _ = hit
    if score < min_score:
        return None

    dist = Levenshtein.distance(query, value)
    auto = score >= auto_accept_score and dist == 0
    return FuzzyMatch(value=value, score=score, edit_distance=dist, needs_confirmation=not auto)
