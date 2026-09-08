"""Gece anomali bülteni birim testleri (ROADMAP Faz 6)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from kervansaray.reports.bulletin import generate_nightly_bulletin
from kervansaray.tools.types import ToolResult

TR = timezone(timedelta(hours=3))
REF_TIME = datetime(2026, 5, 2, 8, 0, 0, tzinfo=TR)


def test_bulletin_no_anomalies(monkeypatch):
    mock_db = MagicMock()
    # Tüm anomali sorguları boş dönsün
    monkeypatch.setattr(
        "kervansaray.reports.bulletin.find_anomalies",
        lambda db, rule, start, end: ToolResult(tool="find_anomalies", params={}, rows=[]),
    )

    res = generate_nightly_bulletin(mock_db, REF_TIME)
    assert res["total_anomalies"] == 0
    assert "herhangi bir anomali tespit edilmedi" in res["bulletin"].lower()


def test_bulletin_with_anomalies_and_llm(monkeypatch):
    mock_db = MagicMock()

    # Birkaç anomali taklit et
    def fake_find(db, rule, start, end):
        if rule == "blacklist":
            return ToolResult(tool="find_anomalies", params={}, rows=[{"plate": "34VIP99"}])
        if rule == "night_entry":
            return ToolResult(tool="find_anomalies", params={}, rows=[{"plate": "38HE907"}])
        return ToolResult(tool="find_anomalies", params={}, rows=[])

    monkeypatch.setattr("kervansaray.reports.bulletin.find_anomalies", fake_find)

    # Mock LLM istemcisi
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "1. Kara listedeki 34VIP99 görüldü.\n2. Gece 03:00'te 38HE907 giriş yaptı."
    mock_client.generate.return_value = mock_resp

    res = generate_nightly_bulletin(mock_db, REF_TIME, client=mock_client)
    assert res["total_anomalies"] == 2
    assert "34VIP99" in res["bulletin"]
    assert "38HE907" in res["bulletin"]
    mock_client.generate.assert_called_once()


def test_bulletin_fallback_when_llm_fails(monkeypatch):
    mock_db = MagicMock()

    def fake_find(db, rule, start, end):
        if rule == "overstay":
            return ToolResult(tool="find_anomalies", params={}, rows=[{"plate": "06ABC06"}])
        return ToolResult(tool="find_anomalies", params={}, rows=[])

    monkeypatch.setattr("kervansaray.reports.bulletin.find_anomalies", fake_find)

    # LLM hata versin
    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("API key quota exceeded")

    res = generate_nightly_bulletin(mock_db, REF_TIME, client=mock_client)
    assert res["total_anomalies"] == 1
    # Fallback devreye girmeli
    assert "Uzun Kalış (48+ Saat)" in res["bulletin"]
    assert "06ABC06" in res["bulletin"]
