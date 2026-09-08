"""Kervansaray Query Pipeline testleri."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from kervansaray.query_pipeline import format_narrative, run_query
from kervansaray.tools.types import ToolResult


def test_empty_query():
    db = MagicMock()
    res = run_query("   ", db)
    assert res["status"] == "error"
    assert "boş olamaz" in res["narrative"]
    assert res["tool_call"] is None


def test_out_of_scope_declined():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "response": "Bu soru otopark ve araç hareketleri kapsamı dışındadır.",
        "function_call": None,
        "provider": "gemini",
    }

    res = run_query("Hava yarın nasıl olacak?", db, client=mock_client)
    assert res["status"] == "declined"
    assert res["tool_call"] is None
    assert "kapsamı dışındadır" in res["narrative"]
    assert res["provider"] == "gemini"


def test_aggregate_events_flow():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "function_call": {
            "name": "aggregate_events",
            "args": {
                "start": "2026-04-15T00:00:00+03:00",
                "end": "2026-04-16T00:00:00+03:00",
                "metric": "count",
            },
        },
        "response": None,
        "provider": "gemini",
    }

    with patch("kervansaray.query_pipeline.dispatch_tool") as mock_dispatch:
        mock_dispatch.return_value = ToolResult(
            tool="aggregate_events",
            params={"metric": "count"},
            scalar=42,
            rows=[{"count": 42}],
        )

        res = run_query(
            "15 Nisan'da kaç araç geçti?",
            db,
            as_of=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
            client=mock_client,
        )

        assert res["status"] == "success"
        assert res["tool_call"]["name"] == "aggregate_events"
        assert res["tool_result"]["scalar"] == 42
        assert "42 araç hareketi gerçekleşti" in res["narrative"]


def test_occupancy_flow():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "function_call": {
            "name": "occupancy",
            "args": {},
        },
        "response": None,
        "provider": "gemini",
    }

    with patch("kervansaray.query_pipeline.dispatch_tool") as mock_dispatch:
        mock_dispatch.return_value = ToolResult(
            tool="occupancy",
            params={},
            scalar=18,
            rows=[{"plate": "34ABC123"}],
        )

        res = run_query("Şu an kaç araç var?", db, client=mock_client)
        assert res["status"] == "success"
        assert res["tool_call"]["name"] == "occupancy"
        assert "18 araç bulunuyor" in res["narrative"]


def test_vehicle_history_flow():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "function_call": {
            "name": "vehicle_history",
            "args": {"plate": "34ABC123"},
        },
        "response": None,
        "provider": "gemini",
    }

    with patch("kervansaray.query_pipeline.dispatch_tool") as mock_dispatch:
        mock_dispatch.return_value = ToolResult(
            tool="vehicle_history",
            params={"plate": "34ABC123"},
            scalar={"is_inside": True},
            rows=[{"direction": "entry"}],
        )

        res = run_query("34ABC123 nerede?", db, client=mock_client)
        assert res["status"] == "success"
        assert "34ABC123" in res["narrative"]
        assert "otoparkta" in res["narrative"]


def test_llm_exception_handled():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.PROVIDER = "gemini"
    mock_client.generate.side_effect = RuntimeError("API baglanti hatasi")

    res = run_query("Dün kaç araç girdi?", db, client=mock_client)
    assert res["status"] == "error"
    assert "Dil modeli sorguyu işlerken bir servis veya bağlantı hatası oluştu" in res["narrative"]
    assert res["tool_call"] is None


def test_format_narrative_anomalies_and_query():
    # Anomalies
    r_anom = ToolResult(
        tool="find_anomalies",
        params={},
        rows=[{"plate": "34XYZ99", "reason": "overstay"}],
    )
    narr = format_narrative("find_anomalies", {"rule": "overstay"}, r_anom)
    assert "1 adet 'overstay' anomalisi tespit edildi" in narr

    # Query events
    r_ev = ToolResult(
        tool="query_events",
        params={},
        rows=[{"plate": "34A1"}, {"plate": "34A2"}],
        truncated=True,
    )
    narr_ev = format_narrative("query_events", {}, r_ev)
    assert "2 araç geçiş kaydı bulundu (ilk 50 kayıt listeleniyor)" in narr_ev


def test_query_cache_basic_and_ttl():
    from kervansaray.query_pipeline import QueryCache

    cache = QueryCache(max_size=2, short_ttl=0.05, long_ttl=10.0)
    cache.set("k1", {"data": 1}, is_dynamic=False)
    cache.set("k2", {"data": 2}, is_dynamic=True)

    assert cache.get("k1") == {"data": 1}
    assert cache.get("k2") == {"data": 2}

    # Eviction test (max_size=2, add 3rd)
    cache.set("k3", {"data": 3}, is_dynamic=False)
    assert len(cache) == 2
    assert cache.get("k1") is None  # k1 en eski, atildi

    # Short TTL expiry
    import time
    time.sleep(0.06)
    assert cache.get("k2") is None
    assert cache.get("k3") == {"data": 3}


def test_run_query_caching_integration():
    from kervansaray.query_pipeline import query_cache

    query_cache.clear()
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "function_call": {
            "name": "aggregate_events",
            "args": {"metric": "count", "start": "2026-04-15", "end": "2026-04-16"},
        },
        "response": None,
        "provider": "gemini",
    }

    with patch("kervansaray.query_pipeline.dispatch_tool") as mock_dispatch:
        mock_dispatch.return_value = ToolResult(
            tool="aggregate_events",
            params={},
            scalar=77,
            rows=[{"count": 77}],
        )

        # 1. cagri: cache miss, LLM cagirilir
        res1 = run_query("15 Nisan'da kaç araç geçti?", db, client=mock_client)
        assert res1["cached"] is False
        assert mock_client.generate.call_count == 1

        # 2. cagri: cache hit, LLM cagirILMAZ!
        res2 = run_query("15 Nisan'da kaç araç geçti?", db, client=mock_client)
        assert res2["cached"] is True
        assert mock_client.generate.call_count == 1  # degismedi!
        assert res2["tool_result"]["scalar"] == 77

        # 3. cagri: use_cache=False ile zorla taze cagri
        res3 = run_query(
            "15 Nisan'da kaç araç geçti?", db, client=mock_client, use_cache=False
        )
        assert res3["cached"] is False
        assert mock_client.generate.call_count == 2


def test_search_notes_pipeline_flow():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "function_call": {
            "name": "search_notes",
            "args": {"query": "VIP"},
        },
        "response": None,
        "provider": "gemini",
    }

    with patch("kervansaray.query_pipeline.dispatch_tool") as mock_dispatch:
        mock_dispatch.return_value = ToolResult(
            tool="search_notes",
            params={"query": "VIP"},
            rows=[{
                "id": 1,
                "author": "Yönetim",
                "body": "VIP misafir araçları Doğu Otoparkına alınır.",
            }],
        )

        res = run_query("VIP araç prosedürü nedir?", db, client=mock_client)
        assert res["status"] == "success"
        assert res["tool_call"]["name"] == "search_notes"
        assert "'VIP' ile ilgili 1 adet not bulundu" in res["narrative"]


def test_query_pipeline_error_does_not_leak_internals():
    db = MagicMock()
    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError(
        "ConnectionError: https://generativelanguage.googleapis.com/...key=SECRET_LEAK"
    )

    res = run_query("Otoparkta kaç araç var?", db, client=mock_client)
    assert res["status"] == "error"
    assert "SECRET_LEAK" not in res["narrative"]
    assert "ConnectionError" not in res["narrative"]
    assert "Dil modeli sorguyu işlerken bir servis veya bağlantı hatası oluştu" in res["narrative"]

