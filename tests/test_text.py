"""CILEKAI'dan tasinan metin yardimcilari icin temel testler."""
import pytest

from kervansaray.text import (
    best_match,
    canonicalize,
    normalize_query,
    parse,
    to_ascii,
    turkish_lower,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("İSTANBUL", "istanbul"),
        ("Ilgın", "ılgın"),
        ("ÇAĞLAYAN Şişli", "çağlayan şişli"),
    ],
)
def test_turkish_lower(raw, expected):
    assert turkish_lower(raw) == expected


def test_to_ascii_and_normalize():
    assert to_ascii("Şişli  Güngören") == "sisli  gungoren"
    assert normalize_query("  Dün   GECE  ") == "dün gece"


@pytest.mark.parametrize(
    "raw", ["34 abc 123", "34-ABC-123", "34abc123", "06 B 1234", "34 AB 123", "34 ABC 12"]
)
def test_valid_plates(raw):
    p = parse(raw)
    assert p.valid, p.reason
    assert p.canonical == canonicalize(raw)


@pytest.mark.parametrize("raw", ["99 XX 11", "00 A 1234", "34ABCD1", "34 A 1", "abc"])
def test_invalid_plates(raw):
    assert not parse(raw).valid


def test_canonical_form():
    assert canonicalize("34 abc 123") == "34ABC123"
    assert canonicalize("34-abc-123") == "34ABC123"


def test_fuzzy_never_auto_accepts_edit_distance_one():
    # PROJECT_BRIEF S3.8: edit distance 1 asla otomatik kabul edilmez.
    known = ["34ABC123", "06XYZ99", "35KLM4321"]
    exact = best_match("34ABC123", known)
    assert exact is not None and not exact.needs_confirmation

    near = best_match("34ABC124", known)
    assert near is not None
    assert near.value == "34ABC123"
    assert near.edit_distance == 1
    assert near.needs_confirmation is True

    assert best_match("99ZZZ000", known) is None
