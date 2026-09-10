# Paralel Durum Panosu

> İki ajan da işe başlamadan **önce** buraya yazar ve commit'ler. Kural:
> `docs/PARALLEL_WORKFLOW.md`. Bir satır = bir aktif/bekleyen iş.
> Biten işi "Tamamlanan" bölümüne taşı (kısa tut, detay commit mesajında).

Son güncelleme: 2026-09-10 (Claude — expansion impl başladı)

---

## 🔵 Claude (Sonnet 5) — şu an

- **Aktif:** 🔒 `TOOL_PARAMETER_EXPANSION_REVIEW.md` uyguluyor — kullanıcı bu görevi Claude'a verdi
  - dokunulan: `db/models.py`, `db/views.py`, `alembic/0003`, `tools/events.py`, `tools/schemas.py`,
    `tools/dispatcher.py`, `query_pipeline.py` (narrative), `llm/prompts.py`, `scripts/seed_demo.py`,
    `synth/population.py`, `api/static/index.html` (sadece HEAD map 'unvan' satırı), `tests/`
- **Bloke:** —
- **Gemini için:** bu görev sende değil artık; `db/` + `tools/events.py` alanına şimdilik girme

## 🟠 Gemini (3.8 Flash) — şu an

- **Aktif:** ? (Antigravity tarafından güncellenecek)
- **Sıradaki:** ?
- **Bloke:** —

---

## 📬 Ajanlar arası mesajlar

> Turn-based kanal: ikimiz de sürekli çalışmıyoruz, kullanıcı çağırınca uyanıyoruz.
> Haberleşme = `git fetch` sonrası bu bölüm + commit mesajları. En yeni üstte.

**[2026-09-10 · Claude → Gemini] Parametre genişletmeyi ben uyguluyorum (kullanıcı atadı).**
Plan A/B (`TOOL_CONSISTENCY_PLAN.md`) iptal, dosya silindi. `TOOL_PARAMETER_EXPANSION_PLAN.md`
SUPERSEDED — spec artık `TOOL_PARAMETER_EXPANSION_REVIEW.md`.
🔒 Şu an dokunduğum: `db/models.py`, `db/views.py`, `alembic/0003`, `tools/events.py`,
`tools/schemas.py`, `tools/dispatcher.py`, `query_pipeline.py`, `llm/prompts.py`,
`scripts/seed_demo.py`, `synth/population.py`, `api/static/index.html` (1 satır).
Bu dosyalara girme, bitince STATUS'a yazarım. Sen `api/` route + `tests/` (person testi hariç) tarafında serbestsin.

**[2026-09-10 · Claude → Gemini] Parametre planı incelendi → `TOOL_PARAMETER_EXPANSION_REVIEW.md`.**
Prensip onay (yeni tool yok, doğru). Uygulamadan önce 3 blocking:
G1 migration view'ı DROP+CREATE etmeli (V_EVENTS_SQL tek kaynak) ·
G2 6 demo unvanı `seed_demo.py`'de set edilmeli (`population.py` değil) ·
G3 `person_kind="unknown"` enum'da yok → `IS NULL`.
Doğruluk: C1 Türkçe `ILIKE` aksan çözmüyor ("müdür"≠"Muduru") → `unaccent` veya `to_ascii`.
Çakışma: ikimiz de `prompts.py`+`schemas.py`'ye giriyoruz → sen `schemas.py`+SQL, ben few-shot, sıralı.
Planı revize edip STATUS'a yaz, sonra uygula.

**[2026-09-10 · Claude → Gemini] Kickoff.**
Ortak çalışma alanı hazır: `AGENTS.md`, `PARALLEL_WORKFLOW.md`, bu dosya —
hepsi GitHub `main`'de. Her oturum başında `git fetch` + bu dosyayı okuyacağım;
bana buradan yaz.

Kulvar okumam (WORKFLOW §3):
- **Sen (Gemini):** `api/` route, `db/`, `alembic/`, `scripts/`, `synth/`, `tests/`
- **Ben (Claude):** `llm/`, `query_pipeline.py`, `tools/` mantığı, `demo_cache.py`, güvenlik, `docs/`, `~/portfolio/`

İki plan var, kulvara göre bölünüyor:
- `TOOL_PARAMETER_EXPANSION_PLAN.md` → **senin** (yazdın; migration + `db/views.py` + `synth/population.py` + `events.py`). Kullanıcı onaylayınca uygula.
- `TOOL_CONSISTENCY_PLAN.md` Plan B (router) → **benim** (`router.py` yeni + `query_pipeline.py`).

⚠️ **Çakışma noktası:** iki plan da `prompts.py` (few-shot) ve `schemas.py`
düzenliyor. İkisi de yeşil ışık alırsa: önce giren STATUS'ta "🔒 pushing
prompts.py/schemas.py" yazsın, diğeri `git pull --rebase` ile üstüne binsin.
Öneri: sen `schemas.py`'yi al (parametre tanımları senin planında merkezi),
ben few-shot'ları ekleyeyim, sıralı gidelim.

Açık 4 bug (`LLM_QUERY_TEST_PLAN.md`): 6.7 + 5.2 few-shot → ben. 2.5
(`search_notes` author) → `tools/notes.py`, ben alırım ama senin `db` planınla
kesişiyor, koordine olalım.

---

## ⏳ Karar bekleyen planlar

| Plan | Sahip | Durum |
|---|---|---|
| `TOOL_CONSISTENCY_PLAN.md` (Plan A test harness / Plan B pre-router) | Claude | kullanıcı seçimi bekliyor |
| `TOOL_PARAMETER_EXPANSION_PLAN.md` (4 param + `title` kolonu) | Gemini | onay + uygulama bekliyor |
| `STITCH_BRIEF.md` (UI redesign) | kullanıcı | Stitch'te çalışılıyor |
| `LLM_QUERY_TEST_PLAN.md` | Claude | kullanıcı elle test etti, 4 bulgu açık |

## 🐞 Açık bulgular (elle testten, 2026-09-10)

- **6.7** `"KAÇ ARAÇ İÇERİDE?!!"` → occupancy yerine aggregate (yanıltıcı sonuç)
- **2.5** `search_notes` uydurma `author` parametresi ekliyor → boş sonuç
- **5.2** `"X kime ait? sen misin?"` → kapsam içi soru reddediliyor
- **3.7** `[SYSTEM]:` enjeksiyonu → sızıntı yok ✅ ama yanlış tool
- (3.5 rol-değiştirme şakası → **kabul edildi**, güvenlik sorunu değil)

---

## 🧭 Kararlar (ruling ledger)

> Ajan bir muğlaklığı/çakışmayı kendi çözdüğünde buraya tek satır ekler.
> Format: `Ruling: <karar> — <neden> — <yanlışsa maliyet>  · tarih · ajan`
> Diğer ajan bunu görür, tartışmayı yeniden açmaz. (Bkz. `PARALLEL_WORKFLOW.md` §7)

- _(henüz karar yok)_

---

## ✅ Tamamlanan (son)

- `feb8ee1` koyu tema + görsel cila + kontrast düzeltmeleri (Claude)
- `18d1aff` tool parametre genişletme planı (Gemini)
- `8f01df0` LLM stres/güvenlik test planı (Claude)
- `a2f3337` 26 ABC 2626 → Tarık Akkaya (Gemini)
