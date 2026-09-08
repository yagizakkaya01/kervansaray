from unittest.mock import patch

from kervansaray.api import create_app
from kervansaray.api.rate_limit import RateLimiter, limiter
from kervansaray.query_pipeline import query_cache
from kervansaray.text.turkish import to_ascii


def test_rate_limiter_sliding_window():
    rl = RateLimiter(per_minute=3, per_day=5)
    ip = "10.0.0.1"

    # 1, 2, 3 istek serbest
    for _ in range(3):
        allowed, err = rl.is_allowed(ip)
        assert allowed is True
        assert err is None

    # 4. istek dakikalik limiti asmali
    allowed, err = rl.is_allowed(ip)
    assert allowed is False
    assert "Dakikalık" in err

    # Farkli IP etkilenmemeli
    allowed_other, _ = rl.is_allowed("10.0.0.2")
    assert allowed_other is True


def test_query_route_enforces_rate_limit(monkeypatch):
    limiter.clear()
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    fake_result = {
        "status": "success",
        "provider": "gemini",
        "narrative": "Test yaniti",
        "tool_calls": [],
        "table": {"columns": [], "rows": []},
        "row_count": 0,
        "scalar_value": None,
        "elapsed_seconds": 0.05,
        "cached": False,
    }

    with patch("kervansaray.api.routes_query.run_query", return_value=fake_result):
        # 5 serbest metin istegi gonder
        for i in range(5):
            r = c.post(
                "/api/query",
                json={"query": f"Farkli serbest soru {i}"},
                headers={"X-Forwarded-For": "198.51.100.1"},
            )
            assert r.status_code == 200

        # 6. istek dakikalik rate limit'e takilmali (429)
        r_blocked = c.post(
            "/api/query",
            json={"query": "Altinci soru"},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        assert r_blocked.status_code == 429
        assert "Dakikalık soru limitine" in r_blocked.get_json()["error"]


def test_cached_query_bypasses_rate_limit():
    limiter.clear()
    query_cache.clear()

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    cached_q = "Hazir chip sorusu"
    cache_key = f"{to_ascii(cached_q.lower())}:now"
    cached_payload = {
        "status": "success",
        "provider": "gemini",
        "narrative": "Hazir yanit",
        "tool_calls": [],
        "table": {"columns": [], "rows": []},
        "row_count": 0,
        "scalar_value": None,
        "elapsed_seconds": 0.0,
        "cached": True,
    }
    query_cache.set(cache_key, cached_payload, is_dynamic=False)

    # IP'nin kotasini tamamen tuket
    ip = "203.0.113.5"
    for _ in range(5):
        limiter.is_allowed(ip)

    # Kotasi dolmus IP yeni soru sorarsa 429 alir
    r_new = c.post(
        "/api/query",
        json={"query": "Yeni soru"},
        headers={"X-Forwarded-For": ip},
    )
    assert r_new.status_code == 429

    # AMA ayni IP onbellekteki hazir soruyu sorarsa 200 doner (0ms, $0 maliyet)
    r_cached = c.post(
        "/api/query",
        json={"query": cached_q},
        headers={"X-Forwarded-For": ip},
    )
    assert r_cached.status_code == 200
    assert r_cached.get_json()["cached"] is True
    assert r_cached.get_json()["narrative"] == "Hazir yanit"
