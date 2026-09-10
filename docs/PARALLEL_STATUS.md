# Paralel Durum Panosu

> İki ajan da işe başlamadan **önce** buraya yazar ve commit'ler. Kural:
> `docs/PARALLEL_WORKFLOW.md`. Bir satır = bir aktif/bekleyen iş.
> Biten işi "Tamamlanan" bölümüne taşı (kısa tut, detay commit mesajında).

Son güncelleme: 2026-09-10

---

## 🔵 Claude (Sonnet 5) — şu an

- **Aktif:** yok — bu protokol dosyalarını yazıp bıraktı
- **Sıradaki:** kullanıcı kararı bekliyor → `TOOL_CONSISTENCY_PLAN.md` (Plan A / B)
- **Bloke:** —

## 🟠 Gemini (3.8 Flash) — şu an

- **Aktif:** ? (Antigravity tarafından güncellenecek)
- **Sıradaki:** ?
- **Bloke:** —

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
