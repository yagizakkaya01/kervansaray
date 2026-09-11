"""Public yazma yuzeyi testleri (ERROR.md E1): tescil upsert, demo reset,
rate-limit reset. Bu uclar public demo'da (bae3c7a) yaziya acildi; koruyan
katmanlar (`_clean_text`, reset cooldown, `clear_ip` IP kapsami) su ana kadar
elle dogrulanmisti, otomatik testi yoktu.
"""
from __future__ import annotations


def test_upsert_strips_html_tags_from_name(client):
    r = client.post(
        "/api/registry/upsert",
        json={"plate": "34 test 01", "name": "<b>x</b> Ali", "kind": "guest"},
    )
    assert r.status_code == 200
    assert r.get_json()["record"]["name"] == "x Ali"


def test_upsert_truncates_overlong_fields(client):
    r = client.post(
        "/api/registry/upsert",
        json={
            "plate": "34 test 02",
            "name": "A" * 90,
            "address": "B" * 90,
            "contact": "C" * 90,
            "kind": "guest",
        },
    )
    assert r.status_code == 200
    rec = r.get_json()["record"]
    assert len(rec["name"]) == 60
    assert len(rec["address"]) == 80
    assert len(rec["contact"]) == 60


def test_upsert_invalid_kind_falls_back_to_guest(client):
    r = client.post(
        "/api/registry/upsert",
        json={"plate": "34 test 03", "name": "Test Kisi", "kind": "operator_admin"},
    )
    assert r.status_code == 200
    assert r.get_json()["record"]["kind"] == "guest"


def test_upsert_unregistered_reverts_demo_plate_to_default(client):
    """kind=unregistered -> vehicle/person silinir, GET /api/registry fabrika
    varsayilanina (DEMO_SCENARIO_PLATES) geri duser."""
    plate = "34 KAY 44"
    r1 = client.post(
        "/api/registry/upsert",
        json={"plate": plate, "name": "Ozel Isim", "kind": "guest"},
    )
    assert r1.status_code == 200

    r2 = client.post("/api/registry/upsert", json={"plate": plate, "kind": "unregistered"})
    assert r2.status_code == 200

    listing = client.get("/api/registry").get_json()["registry"]
    rec = next(x for x in listing if x["plate"] == plate)
    assert rec["name"] == "Sayın Kaya"


def test_demo_reset_cooldown_blocks_immediate_second_call(client, monkeypatch):
    from kervansaray.api import routes_registry

    monkeypatch.setattr(routes_registry, "_last_reset_at", 0.0)

    r1 = client.post("/api/demo/reset")
    assert r1.status_code == 200
    assert r1.get_json()["ok"] is True

    r2 = client.post("/api/demo/reset")
    assert r2.status_code == 429
    assert "tekrar deneyin" in r2.get_json()["error"]


def test_demo_reset_repopulates_curated_cache(client, monkeypatch):
    """demo/reset sonrasi kuratorlu sorular (demo_cache.warm) hemen dolu olmali,
    aksi halde 16 hazir soru restart'a kadar canli LLM'e duser."""
    from kervansaray.api import routes_registry
    from kervansaray.query_pipeline import query_cache
    from kervansaray.text.turkish import to_ascii

    monkeypatch.setattr(routes_registry, "_last_reset_at", 0.0)
    query_cache.clear()

    r = client.post("/api/demo/reset")
    assert r.status_code == 200

    key = f"{to_ascii('Şu an sahada kaç araç var?'.strip().lower())}:now"
    cached = query_cache.get(key)
    assert cached is not None
    assert cached["status"] == "success"
    assert cached["tool_call"]["name"] == "occupancy"


def test_rate_limit_reset_only_clears_calling_ip(client, monkeypatch):
    """POST /api/rate-limit/reset yalniz cagiran IP'yi temizlemeli, baska
    IP'nin dolu kotasina dokunmamali."""
    from kervansaray.api.rate_limit import limiter

    monkeypatch.setattr(limiter, "per_minute", 1)
    limiter.clear()
    ip_a, ip_b = "203.0.113.10", "203.0.113.20"

    assert limiter.is_allowed(ip_a)[0] is True
    assert limiter.is_allowed(ip_b)[0] is True
    assert limiter.is_allowed(ip_a)[0] is False
    assert limiter.is_allowed(ip_b)[0] is False

    r = client.post("/api/rate-limit/reset", headers={"X-Forwarded-For": ip_a})
    assert r.status_code == 200

    assert limiter.is_allowed(ip_a)[0] is True
    assert limiter.is_allowed(ip_b)[0] is False
