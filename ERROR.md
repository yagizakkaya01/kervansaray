# ERROR.md — Bilinen Hatalar & Açık Bulgular

> Kaynak: `urettiklerim.html` (public demo) odaklı tam repo incelemesi, 2026-09-09.
> Kapsam: `bae3c7a` (feat: guardrail/registry/audit) + `f6c0118` (rate-limit) +
> paralel geliştirme sonrası durum.

---

## ✅ Kapatıldı

`bae3c7a` public demoyu yazılabilir yaptı. Önce hepsi `@operator_only` ile
kilitlendi (`9a48a24` + `aa5044d`). Sonra **ürün kararı**: tescil düzenleme /
kayıtsız aracı tescil / demo reset **bilinçli interaktif demo özellikleri**
(sentetik veri + her an fabrika sıfırlama). `d1...` ile yazma uçları public'e
geri açıldı, **görünmez** sıkılaştırma eklendi:

| Açık | Nihai durum |
|---|---|
| Stored XSS: `renderRegistryTable` / `showToast` `r.name`/`address`/`contact` `innerHTML`'e escape'siz | **Kapalı.** Frontend `esc()` + sunucuda `_clean_text()` (HTML etiketlerini sök, uzunluk sınırı: name 60 / address 80 / contact 60). İki katman. |
| `POST /api/demo/reset` griefing/DoS (spam TRUNCATE+reseed) | **Kapalı.** 8 sn modül-seviye cooldown → spam'de 429. |
| `POST /api/rate-limit/reset` global `limiter.clear()` (tüm IP'ler) + `query_cache.clear()` | **Kapalı.** Artık yalnız çağıran IP'yi temizler (`limiter.clear_ip`), global önbelleğe dokunmaz. Public. |
| `reset_demo` `warm_cache()` çağırıp hemen `query_cache.clear()` yapıyordu (E5 sınıfı) | **Kapalı.** Sıra düzeltildi: önce clear, en son warm. |
| `upsert` sonrası kuratörlü cevaplar kayboluyordu | **Kapalı.** `upsert` sonrası `demo_cache.warm()`. |

- `src/kervansaray/api/guards.py` (`@operator_only`) artık kullanılmıyor → **silindi**.
- `POST /events` (ingest) hâlâ `ENABLE_OPERATOR_ROUTES` ile kilitli (değişmedi).
- Sorgu hattı (`/api/query`) salt-okunur — tool'lar yalnız SELECT.
- `portfolio/Caddyfile`: `/api/registry* /api/demo* /api/rate-limit*` proxy'li; `/api/events*` değil.

---

## 🟠 Açık — Yüksek

### E1 · Yeni yüzeyin sıfır testi
**Nerede:** `tests/` — 20 test dosyası; `routes_registry.py`, `check_query_safety`,
`build_audit_metadata`, `demo_cache.py`, `_clean_text`, reset cooldown için **hiçbiri yok**.
**Risk:** ~1500 satır yeni kod. Bir sonraki refactor `_clean_text`'i veya
`renderRegistryTable`'daki `esc()`'i sessizce geri alabilir → stored XSS geri döner.
**Düzeltme:** `tests/test_registry.py` — Flask test client:
- `POST /api/registry/upsert` `name="<b>x</b> Ali"` → kayıtlı name `"x Ali"` (tag sökülmüş)
- name > 60 char → kesiliyor
- `POST /api/demo/reset` iki kez arka arkaya → 2. çağrı 429
- `POST /api/rate-limit/reset` → yalnız çağıran IP; başka IP'nin kotası duruyor
- demo reset sonrası kuratörlü soru (`query_cache`) hâlâ dolu
- `check_query_safety`: `"DROP TABLE"` → `(False, …)`, normal Türkçe → `(True, …)`, `"5 -- 6"` → şu an `(False, …)` (bkz. E3)

`conftest.py`'de test DB fixture'ı var (`test_ingest.py` kullanıyor).

### E2 · `Person.contact` — public `GET /api/registry`'de dönüyor
**Nerede:** `db/models.py` `Person.contact` + migration `0002` + `routes_registry.py`
`list_registry` her kayıtta `"contact"` döndürüyor; endpoint public.
**Durum:** Veri sentetik ve tescil defteri artık **kasıtlı** interaktif demo —
"İletişim" sütunu demonun bir parçası. Yani düşük öncelik. Yine de kardeş
`portfolio/AGENTS.md` deseni ("public endpoint contact döndürmemeli") ile çelişiyor;
gerçek veri hiç girilmemeli (upsert formu placeholder'ları sentetik tutulmalı) ve
`_clean_text` contact'ı da 60 char'a sınırlıyor. İstenirse "İletişim" sütununu
tamamen kaldırmak en temizi.
Frontend `${esc(r.contact || '—')}` zaten `undefined` → `'—'` gösteriyor, uyumlu.

---

## 🟡 Açık — Orta

### E3 · `check_query_safety` yanlış pozitif + güvenlik değeri yok
**Nerede:** `src/kervansaray/query_pipeline.py:~195-220`
```python
r"--\s*",        # herhangi bir çift tire (whitespace opsiyonel)
r"/\*.*?\*/",    # herhangi bir /* ... */
```
**Sorun A:** `r"--\s*"` kullanıcının sorusundaki her `--`'yi yakalıyor →
`"14 EV 669 -- kayıtlı mı?"`, `"5--6 civarı"`, markdown liste → "SQL Manipülasyon Engellendi".
**Sorun B:** Tool katmanı parametreli SQLAlchemy; LLM SQL değil tool call üretiyor.
Kullanıcı "DROP TABLE" yazsa hiçbir yerde ham SQL çalışmaz — bu fonksiyon bir şeyi
**engellemiyor**, sadece audit künyesine "🛡️ Temiz" yazmak için var.
**Sorun C:** `run_query`'de safety, **cache'ten önce** çalışıyor (adım 0 → adım 1) →
16 kuratörlü cevap her seferinde bu regex'ten geçiyor.
**Düzeltme:** `--` desenini daralt → `r"(^|\s);?\s*--(\s|$)"` (SQL yorumu bağlamı),
`/* */`'ı kaldır; safety'yi cache kontrolünden **sonraya** al; yorum satırına
"defense-in-depth teatral, asıl koruma parametreli sorgular" yaz.
Injection desenleri (`jailbreak`, `ignore + talimat`) makul, dursun.

### E4 · `list_registry` `kind`'ı serbest metinden türetiyor
**Nerede:** `routes_registry.py:~73-82`
```python
lbl = (v.label or "").lower()
elif any(w in lbl for w in ("guvenlik", "güvenlik", "manager", "amir")): kind = "manager"
elif any(w in lbl for w in ("vip", "protokol", "baskan", "başkan")):     kind = "vip"
elif any(w in lbl for w in ("terk", "warning", "şüphe", "suphe")):       kind = "warning"
```
**Sorun:** Aracın türü DB'de gerçek kolon değil — `Vehicle.label` (serbest metin adres)
içinde kelime aranarak tahmin ediliyor. `upsert` türü label'a gömüyor, `list` parse ediyor.
**Kırılma:** Operator VIP misafirin adresini "Doğu Otoparkı B-12" yaparsa → label'da
"vip/protokol" geçmez → `kind` `guest`'e düşer → yanlış rozet.
**Ek:** `DEMO_SCENARIO_PLATES` (`routes_registry.py:~31`) 6 plakayı hardcode ediyor —
`seed_demo.py`, `demo_cache.py`, `index.html` `SCENARIOS` ile birlikte **4. kopya**.
**Düzeltme:** `Vehicle`'a gerçek `category`/`kind` kolonu (migration `0003`); `upsert`
yazsın, `list` okusun. 6-plaka tanımını tek modülde topla (`kervansaray/demo_scenarios.py`),
4 dosya import etsin.

### E5 · `rate_limit` `per_day=500` + `DISABLE_RATE_LIMIT` bypass
**Nerede:** `src/kervansaray/api/rate_limit.py:~24, ~33`
- `per_day` varsayılanı `f6c0118`'de 20 → **500**. Paralı NVIDIA API'sinde teorik 500
  çağrı/gün/IP. Kuratörlü cache 16 demo sorusunu bedava karşılıyor (`limiter` hiç
  çağrılmıyor) — sadece özgün sorular kotayı harcıyor. Yine de "bedava portfolyo demosu"
  için yüksek.
- `DISABLE_RATE_LIMIT` env (`1/true/yes`) → `is_allowed` her zaman `True`. Canlı `.env`'de
  yok ama tehlikeli knob.
**Düzeltme:** `per_day`'i 100-150'ye çek. `DISABLE_RATE_LIMIT`'i kaldır veya `.env.example`'da
"SADECE yerel test" uyarısıyla belgele.

---

## 🟢 Açık — Düşük

### E6 · `demo_cache.warm()` hata sonuçlarını da cache'liyor
**Nerede:** `src/kervansaray/demo_cache.py:~96-105`
`try/except` sadece exception yakalıyor. `dispatch_tool` `ToolResult(note="…")` dönerse
(geçersiz `rule`, tarih parse hatası) → `status:"error"` payload'ı 24 saat TTL ile
cache'e yazılır, o kuratörlü soru **restart'a kadar hatalı** cevap verir.
**Düzeltme:** `if res.note: log.warning(...); continue` — hatalıyı cache'e yazma.

### E7 · Review kartı render'ında escape yok
**Nerede:** `src/kervansaray/api/static/index.html:~2080-2121` (`fetchReviewQueue`)
`card.innerHTML = \`… ${item.raw_plate} … ${item.camera_id} …\``, `esc()` yok.
**Neden düşük:** `fetchReviewQueue` sadece `#review-btn` görünürse çalışır → `/api/review`
200 dönerse → `ENABLE_OPERATOR_ROUTES=true`. Public demoda 404 → buton gizli → bu kod
hiç çalışmıyor. Operator-only bağlam + veri operator'ün kendi DB'sinden.
**Düzeltme:** Tutarlılık için aynı `esc()`'i `item.camera_id`, `item.raw_plate`,
`item.candidate_owner`, `e.message`'a uygula.

### E8 · README + `.env.example` bayat / eksik
- `README.md` "Dizin yapısı" bölümü `demo_cache.py`, `routes_registry.py`,
  `routes_query.py`, `tools/*`, `reports/bulletin.py`, `notifications.py`'yi anmıyor —
  hâlâ "sema ve ingest API yazıldıkça eklenecek" diyor. "Gelistirme" bölümü Windows
  venv yolu veriyor (sunucu Linux). `make seed-demo` anlatılmıyor.
- `.env.example`'da yok ama `rate_limit.py` okuyor: `RATE_LIMIT_PER_MINUTE` (10),
  `RATE_LIMIT_PER_DAY` (500), `DISABLE_RATE_LIMIT` (tam bypass).
**Düzeltme:** README ağacını gerçek yapıyla güncelle; `.env.example`'a 3 knob'u
uyarıyla ekle.

### E9 · `search_notes` tüm tabloyu çekip Python'da filtreliyor
**Nerede:** `src/kervansaray/tools/notes.py` (`2b29e6b`'de değişti)
Eski: `WHERE body ILIKE :term LIMIT :limit`. Yeni: `SELECT … FROM notes ORDER BY ts DESC`
(**LIMIT yok**) → tüm notları RAM'e → Türkçe stopword ayıkla → Python'da skorla.
**Risk:** 6 not için önemsiz. `notes` büyürse (gerçek vardiya defteri) her sorguda tüm
tablo çekiliyor — ölçeklenmiyor.
**Düzeltme:** Postgres FTS (`to_tsvector`/`plainto_tsquery`) veya en azından ILIKE ön-filtre
+ üst sınır.

---

## Öncelik

| Öncelik | Maddeler |
|---|---|
| Yüksek | E1 (registry testleri), E2 (contact PII → operator-gate) |
| Orta | E3 (`--` regex), E4 (kind kolonu + tek-kaynak 6 plaka), E5 (per_day 100) |
| Düşük | E6, E7, E8 (README/env), E9 |
