"""Turkce tarih ve zaman cozumleyici testleri."""
from datetime import datetime

from kervansaray.text.dates import TR, extract_time_hint, resolve_time_range

_REF = datetime(2026, 4, 15, 14, 30, 0, tzinfo=TR)  # 15 Nisan 2026 Carsamba


def test_iso_date():
    rng = resolve_time_range("2026-05-20 gunundeki girisler", as_of=_REF)
    assert rng is not None
    start, end = rng
    assert start == datetime(2026, 5, 20, 0, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 5, 21, 0, 0, 0, tzinfo=TR)


def test_turkish_explicit_day_month():
    rng = resolve_time_range("15 Nisan'da hangi araclar geldi?", as_of=_REF)
    assert rng is not None
    start, end = rng
    assert start == datetime(2026, 4, 15, 0, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 4, 16, 0, 0, 0, tzinfo=TR)


def test_turkish_day_month_with_hours():
    rng = resolve_time_range("15 Nisan 2026 02:00 ile 04:00 arasi", as_of=_REF)
    assert rng is not None
    start, end = rng
    assert start == datetime(2026, 4, 15, 2, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 4, 15, 4, 0, 0, tzinfo=TR)


def test_dun_gece():
    rng = resolve_time_range("dun gece kimler girdi?", as_of=_REF)
    assert rng is not None
    start, end = rng
    # 15 Nisan Carsamba -> dun gece: 14 Nisan 20:00 - 15 Nisan 06:00
    assert start == datetime(2026, 4, 14, 20, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 4, 15, 6, 0, 0, tzinfo=TR)


def test_dun():
    rng = resolve_time_range("dun gelen araclar", as_of=_REF)
    assert rng is not None
    start, end = rng
    assert start == datetime(2026, 4, 14, 0, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 4, 15, 0, 0, 0, tzinfo=TR)


def test_month_whole():
    rng = resolve_time_range("Nisan 2026'da toplam kac arac girdi?", as_of=_REF)
    assert rng is not None
    start, end = rng
    assert start == datetime(2026, 4, 1, 0, 0, 0, tzinfo=TR)
    assert end == datetime(2026, 5, 1, 0, 0, 0, tzinfo=TR)


def test_extract_time_hint():
    hint = extract_time_hint("15 Nisan'da kac hareket oldu?", as_of=_REF)
    assert "start=" in hint
    assert "end=" in hint
    assert "2026-04-15" in hint


def test_no_date_returns_none():
    assert resolve_time_range("34ABC123 plakali aracin gecmisi", as_of=_REF) is None
    assert extract_time_hint("hava durumu nasil?", as_of=_REF) == ""
