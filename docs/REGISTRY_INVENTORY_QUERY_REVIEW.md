# İnceleme — `REGISTRY_INVENTORY_QUERY_PLAN.md` (046486e)

> İnceleyen: Claude (Sonnet 5) · 2026-09-10 · canlı DB'ye karşı doğrulandı.
> Sahip: Gemini. Kulvar: `tools/events.py` + `schemas.py` + `prompts.py`.

---

## Verdict

**Problem gerçek** — `vehicles` (tescil envanteri) ile `v_events` (kapı hareketleri)
ayrı gerçeklikler; hiçbir tool `vehicles`'ı saymıyor, model `search_notes`'a kaçıyor.
Kök neden analizin (`_DOMAIN_HINTS` → `tool_choice="required"` → tarih isteyen
`aggregate_events` → kaçış kapısı `search_notes`) **doğru ve keskin**.

**Ama plan iki noktada hatalı:** yanlış sayıyor (R1) ve kötü yere koyuyor (R2).
Önce "kayıtlı/tescilli ne demek" kararı gerekiyor.

---

## 🔴 R1 — "Tescilli" tanımı belirsiz; plan yanlış sayıyı döndürüyor

Canlı DB:

| Yorum | Sayı |
|---|---|
| `SELECT count(*) FROM vehicles` (planın kullandığı) | **205** |
| person_id dolu (sahibi var) | 175 |
| **geçerli tescili var** (`EXISTS registrations WHERE active`) | **63** |
| kapıdan geçmiş tekil plaka | 38 |

205'in 30'u `person_id NULL` + sentetik 82-99 il kodlu gürültü. **"Tescil" =
registration kaydı** → doğru cevap **63** (bu zaten `v_events.registered=true`'nun
tanımı). Plan `count(*) FROM vehicles` → 205 diyor, test "→ 205" assert ediyor.

**Düzeltme:** Önce karar — "kayıtlı araç" = geçerli tescili olan (63) mi, sahibi
olan (175) mi? Muhtemelen `WHERE EXISTS (SELECT 1 FROM registrations r WHERE
r.vehicle_id = v.id AND (r.valid_to IS NULL OR r.valid_to >= now()))`.

## 🔴 R2 — `aggregate_events`'e bindirmek kötü uyum

`aggregate_events`'in sözleşmesi: "**v_events** üzerinde **zaman-pencereli** olay
agregasyonu". `registered_vehicles`:
- farklı tabloyu (`vehicles`) sorguluyor
- `start`/`end`'i yok sayıyor → **koşullu-zorunlu parametre**, küçük model tuzağı
  (plan "required listesi güncellenir veya prompt ile yönetilir" diye geçiştiriyor)
- `direction`, `group_by` anlamsız kalıyor

Bu tam da "6 tool" ilkesinin engellemeye çalıştığı şey: aynı tool içinde
davranışı komple değiştiren bir mod. Yeni tool'dan daha kafa karıştırıcı.

## 🟡 R3 — Daha temiz seçenekler

- **C (öneri, en yalın): yeni sayım yolu YOK.** Sadece:
  1. `search_notes` negatif kuralı (aşağıda, zaten iyi)
  2. Prompt'a: "envanter/kayıt sayısı sorulursa `aggregate_events`
     `metric='unique_plates'` ile kapıdan geçen tekil araç sayısını ver;
     'sistemde kayıtlı toplam tescil' ayrı bir kavram olduğunu belirt."
  Kullanıcı bunu **bir kez** sordu — gerçek recruiter sorusu mu, edge case mi?
- **A: küçük ayrı tool `registry_summary()`** — parametresiz (veya opsiyonel
  `person_kind`), döner `{toplam, aktif_tescil, tur_dağılımı, kara_liste}`.
  Tetikleyicisi net ve ayrık ("envanter" vs "geçiş"). 7. tool ama gerçekten
  ortogonal — `aggregate_events` moduna göre daha AZ kafa karıştırıcı.
- **B: `aggregate_events`'te `start`/`end`'i TÜM metrikler için opsiyonel yap**
  (verilmezse tüm dönem). `registered_vehicles` sadece bir metrik olur,
  koşullu-zorunluluk kalkar. Tablo değişimi hâlâ var ama daha az kötü.

Öncelik sıram: **C > A > B > planın hali.**

## 🟢 R4 — `search_notes` negatif kuralı: iyi, tut

"Sayı/adet/istatistik/envanter sorularında ASLA `search_notes` çağırma" —
`search_notes` şema açıklamasına + sistem prompt'una eklensin. Bu, kaçış
kapısını kapatır ve C seçeneğiyle tek başına çözüm olabilir.

## 🟢 R5 — Kırık testleri Gemini'nin alması: kabul

Not: `test_query_pipeline` narrative testleri benim `610804a`'daki 0-satır
narrative değişikliğimle de etkileşiyor. Düzeltirken `format_narrative`'in
**güncel** halini (query_pipeline.py:116-145) baz al.

## 🟡 R6 — Demo tutarlılığı

Frontend `/api/registry` sadece **6** senaryo plakası gösteriyor. "Kaç kayıtlı
araç" → 63 (veya 205) dersek, kullanıcı 6 görüp farklı sayı duyunca kafası
karışır. Narrative bunu açıklamalı ("6 senaryo aracı + N sentetik arka plan")
ya da sayım yapılacaksa `person_kind` dağılımını da versin.

---

## Önerilen sıra

1. Karar: "kayıtlı araç" tanımı (aktif tescil = 63 öneriyorum)
2. `search_notes` negatif kuralı (R4) — bu tek başına kaçışı durdurur
3. Prompt netleştirme (R3-C)
4. Hâlâ sayım isteniyorsa: `registry_summary()` küçük tool (R3-A), `aggregate_events` overload'ı DEĞİL
