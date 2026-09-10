# İnceleme — `TOOL_PARAMETER_EXPANSION_PLAN.md` (18d1aff)

> ✅ **UYGULANDI** — commit `610804a` (+ index.html cila). Canlıda doğrulandı:
> "güvenlik müdürünün bu ayki giriş çıkışları" → `query_events(person=...)` → 7 satır
> (önce filtresiz 13 dönüyordu). G1–G3 + C1 + C3 kapatıldı. C2 (kelime uyuşmazlığı)
> sınırı: demo 6'lısı seed'de tam metinli; rastgele synth personeli best-effort.
> 9 yeni test (`tests/test_tools_person_filter.py`) + `test_migrations` düzeltildi.

> İnceleyen: Claude (Sonnet 5) · 2026-09-10 · kod tabanına karşı doğrulandı.
> Sahip: Gemini (Antigravity). Kulvar: `db/` + `alembic/` + `synth/` + `tools/events.py`.

---

## Verdict

**Yön doğru — prensip onaylanır.** "Yeni tool değil, parametre" kararı hem
`PROJECT_BRIEF §3.2` ("small set of typed tools") hem `TOOL_CONSISTENCY_PLAN.md`
ile uyumlu. `0002_add_contact_to_persons` birebir emsal.

**Ama plan eksik tanımlı.** Uygulamadan önce 3 blocking boşluk + 3 doğruluk
sorunu kapatılmalı. "45 dk / çok düşük risk" iyimser — view rebuild + seed +
Türkçe eşleşme + testlerle ~2 saat.

---

## Doğru olan

- 6 tool donduruldu, yeni tool yok → küçük model tool seçim doğruluğu korunuyor
- Tüm yeni parametreler opsiyonel (`default=None`) → mevcut 20 test kırılmaz
- Sıfır yeni bağımlılık
- `0002` migration'ı aynı deseni (persons'a kolon ekleme) zaten uygulamış

---

## 🔴 Blocking boşluklar (uygulamadan önce)

### G1 — Migration view'ı DROP+CREATE etmeli, sadece kolon eklemek yetmez
`person_title` alanı `v_events`'e girecekse: PostgreSQL'de view'a `ALTER` ile
kolon eklenmez. `0003` migration'ı:
1. `ALTER TABLE persons ADD COLUMN title VARCHAR(100)`
2. `DROP VIEW v_events` → `CREATE VIEW v_events AS ...` (yeni `p.title AS person_title` ile)
3. Downgrade: ters sıra.
`src/kervansaray/db/views.py :: V_EVENTS_SQL` **tek kaynak** — migration bu
sabiti import etmeli ya da birebir kopyalamalı (test fixture'ı `rebuild_schema`
bu SQL'i kullanıyor, iki yer ayrışırsa testler yalan söyler).
`0002` bu sorunu yaşamadı çünkü `contact` view'a hiç eklenmedi.

### G2 — 6 demo kimliğinin unvanı `seed_demo.py`'de set edilmeli, `population.py`'de değil
Plan `synth/population.py`'de personele unvan atıyor — ama asıl senaryo
(`26 ABC 2626 = Güvenlik Müdürü`) `scripts/seed_demo.py:136`'da:
```python
p = _mk_person(sess, "Tarık Akkaya", PersonKind.staff, contact="...")
```
`_mk_person` imzasına `title=None` eklenip **6 senaryo plakası için açıkça**
unvan verilmeli (`seed_demo.py` + `routes_registry.py :: DEMO_SCENARIO_PLATES`
tutarlı). Rastgele synth personeli için unvan best-effort; demo 6'lısı deterministik.

### G3 — `person_kind` filtresi `"unknown"` değerinde patlar
`PersonKind` enum'u sadece `guest, staff, vendor` (models.py:36). `"unknown"`
gerçek enum değeri **değil** — `v_events`'te eşleşmesiz olay = `person_kind NULL`.
Plandaki `where.append("person_kind = :person_kind")` `person_kind="unknown"`
için hata verir. Doğrusu:
```python
if person_kind == "unknown":
    where.append("person_kind IS NULL")
elif person_kind:
    _check(person_kind in {"guest","staff","vendor"}, ...)
    where.append("person_kind::text = :person_kind")
```
Ayrıca `prompts.py` sözlüğü `person_kind: 'unknown'` diyor — enum'da yok, bu
zaten mevcut bir prompt hatası; bu turda düzelt.

---

## 🟡 Doğruluk sorunları

### C1 — Türkçe: `ILIKE` aksan/harf duyarsız değil
`person_title ILIKE '%güvenlik müdürü%'` → `"Guvenlik Muduru"` (ascii) veya
`"Güvenlik Amiri"` ile **eşleşmez**. Postgres `ILIKE` case-insensitive ama
diacritic-insensitive değil. `search_notes` bunu `to_ascii()` ile çözüyor.
Seçenekler:
- `CREATE EXTENSION IF NOT EXISTS unaccent` + `WHERE unaccent(lower(person_title)) LIKE unaccent(lower(:person))` (migration'a extension satırı)
- veya tool arama terimini `to_ascii()` ile normalize et + unvanları seed'de ascii sakla
- Birini seç, planda yaz. Ham `ILIKE` sessizce boş döner (bkz. bug 6.7 sınıfı).

### C2 — "güvenlik müdürü" ≠ "Güvenlik Amiri" (kelime uyuşmazlığı)
Aksan çözülse bile kullanıcı "müdür" der, synth "amir" atamışsa eşleşme yok.
**Demo 6'lısı için kontrol edilebilir** (seed'de tam metni koy). Rastgele synth
personeli için best-effort — planda bu sınır açıkça yazılmalı, yoksa "çalışmıyor"
bug'ı gelir.

### C3 — `person` parametresi `vehicle_label`'ı kapsamıyor
Bugün "Güvenlik Müdürü" bilgisi `vehicle_label = "Guvenlik Muduru - Nizamiye"`
içinde (seed_demo.py:137). Plan `person` filtresini `person_name OR person_title`
yapıyor, `vehicle_label`'ı atlıyor. Karar: `vehicle_label` rol kaynağı olarak
**terk mi ediliyor** (ERROR.md E4) yoksa `person` filtresi onu da mı taramalı
(`OR vehicle_label ILIKE ...`)? Net yaz.

---

## 🔵 Plan B (router) ile koordinasyon

`TOOL_CONSISTENCY_PLAN.md` Plan B de `prompts.py` few-shot + `schemas.py`
düzenliyor → **çakışma**. Ayrıca:

- Router "güvenlik müdürü" → `26ABC2626` eşlemesini **deterministik** yapabilir
  (6 bilinen plakadan biri). Bu, kırılgan `title ILIKE`'dan daha güvenilir.
- İki yol birden kurulursa: aynı soruyu hem router hem `title` filtresi
  çözmeye çalışır. **Önce hangi katman?** Öneri: router bilinen unvanları
  (`güvenlik müdürü`, `genel müdür` vb.) plakaya çevirir; `title` filtresi
  yalnız router'ın bilmediği serbest unvanlar için fallback.

**Sıralama (kickoff'ta önerilen):** Gemini `schemas.py` param tanımlarını + SQL'i
alır, Claude few-shot'ları ekler; `prompts.py`'ye kim önce girerse STATUS'ta
`🔒 pushing prompts.py` yazar, diğeri rebase.

---

## Önerilen revize kapsam (G1–G3 + C1 kapatılmış)

| Katman | Değişiklik |
|---|---|
| `alembic/versions/0003_*.py` | `persons.title` + `unaccent` extension + `V_EVENTS_SQL` import ederek view DROP/CREATE + downgrade |
| `db/models.py` | `Person.title: Mapped[str \| None] = mapped_column(String(100))` |
| `db/views.py` | `V_EVENTS_SQL`'e `p.title AS person_title` |
| `synth/population.py` | staff'a rastgele gerçekçi unvan (opsiyonel, best-effort) |
| `scripts/seed_demo.py` | `_mk_person(..., title=...)` + 6 senaryo plakasına açık unvan |
| `tools/events.py` | `query_events`: `person` (unaccent'li, name+title[+label?]), `person_kind` (unknown→IS NULL). `aggregate_events`: `plate` (canonicalize), `person_kind` |
| `tools/schemas.py` | tipli param + Türkçe açıklama + "SADECE kullanıcı kişi/unvan belirttiyse doldur" negatif yönerge (bkz. bug 2.5) |
| `llm/prompts.py` | 2 few-shot + `person_kind` sözlüğünden `unknown` düzeltmesi + 0-satır durumunda "X için kayıt yok" net anlatısı |
| `tests/` | `person`/`person_kind` filtre testleri + "müdür" aksan eşleşme testi + 0-satır anlatı testi |

**Efor:** ~2 saat (testler + view rebuild dahil). **Risk:** düşük ama sıfır değil —
yeni parametreler yeni halüsinasyon yüzeyi (2.5 sınıfı). Negatif few-shot + net
0-satır anlatısı şart.
