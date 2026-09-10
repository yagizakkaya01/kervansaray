# Tool Seçim Tutarlılığı — Plan A vs Plan B

> Sorun: LLM sorgu motoru aynı soruya her zaman aynı tool'u seçmiyor; elle
> test yorucu ve tekrarlanamaz. İki farklı yaklaşım var. **Rakip değiller**
> ama neyi çözdükleri farklı — bu dosya karar vermek için ikisini ayırır.
>
> Referans: `src/kervansaray/query_pipeline.py`, `docs/LLM_QUERY_TEST_PLAN.md`,
> `ERROR.md` E1. Tarih: 2026-09-10.

---

## Tek cümlede fark

| | Cevapladığı soru | Türü |
|---|---|---|
| **Plan A** | "Ne kadar tutarlıyız, nerede kırılıyor?" | Ölçüm + regresyon koruması |
| **Plan B** | "Tutarlılığı nasıl artırırız?" | Mimari değişiklik |

Plan A tek başına hiçbir şeyi **düzeltmez**, sadece gösterir.
Plan B düzeltir ama **kanıtın olmaz** — sonraki değişiklik sessizce bozabilir.

---

# PLAN A — Otomatik test / eval harness

**Amaç:** Elle 90 soru sormayı tekrarlanabilir bir komuta çevirmek. Prompt
veya router her değiştiğinde "kaç geçti / kaç kaldı" raporu almak.

## Kapsam

### A1 — pytest eval (çekirdek, öneri)
- Mevcut `tests/` + `conftest.py` DB fixture'ını kullanır; `run_query()`'yi
  **doğrudan** çağırır (HTTP yok, rate limit yok, yer gerçeği belli).
- `tests/eval/cases.yaml` — her satır: soru · beklenen tool · argüman kısıtları
  (ör. `metric == count`) · narrative kuralları (`not-contains "HACKED"`).
  `docs/LLM_QUERY_TEST_PLAN.md`'deki 90 soru buraya taşınır.
- `tests/eval/test_tool_selection.py` — cases.yaml'ı okur, çalıştırır, assert eder.
- **Determinizm iki mod:**
  - `--live`: gerçek NVIDIA çağrısı, eşik "90'da ≥ 85 geçsin", nightly CI.
  - `--replay`: LLM cevapları bir kez kaydedilir (cassette), PR CI'da %100
    tekrarlanabilir. Model kaprisini test dışı bırakır.
- ERROR.md **E1'i kapatır** (yeni yüzeyin sıfır testi).

### A2 — promptfoo (opsiyonel, A1'in üstüne)
- `promptfooconfig.yaml` → `http` provider → `/api/query`.
- `promptfoo redteam`: senin yazmadığın yüzlerce injection / jailbreak / PII
  varyasyonunu **otomatik üretip** dener.
- HTML rapor, GitHub Actions entegrasyonu.
- Repo: `promptfoo/promptfoo` (Mart 2026'da OpenAI aldı, hâlâ OSS).

### A3 — garak (opsiyonel, derin güvenlik taraması)
- NVIDIA'nın kendi "LLM açık tarayıcısı". `rest` generator → `/api/query`.
- Probe'lar: `promptinject`, `dan` (jailbreak), `leakreplay` (veri sızıntısı), `xss`.
- Repo: `NVIDIA/garak`.

## Değerlendirme

| | |
|---|---|
| **Çözer** | Ölçüm, regresyon koruması, güvenlik açığı taraması, E1 |
| **Çözmez** | Tool seçim yüzdesini **kendi başına artırmaz** |
| **Efor** | A1 ~yarım gün · A2 ~2 saat · A3 ~2 saat |
| **Risk** | Düşük — sadece test kodu, prod hattına dokunmaz |
| **Bağımlılık** | A1: sıfır (pytest zaten var) · A2/A3: dev bağımlılığı (npm/pip) |
| **Bakım** | cases.yaml büyüdükçe güncelleme; cassette'leri periyodik yenileme |

---

# PLAN B — Deterministik pre-router + iyileştirmeler

**Amaç:** Modeli kolay kararlardan çıkarmak. Aynı girdi → aynı tool, her seferinde.
Kod tabanındaki mevcut iki deterministik katmanın (`demo_cache` exact-match,
guardrail regex) üçüncüsü.

## Kapsam

### B1 — `src/kervansaray/router.py` (çekirdek)
- `route_intent(query) -> RouteHint | None`
- Türkçe anahtar kelime setleri + plaka regex + `to_ascii` normalizasyon.
- Güven skoru: net eşleşme → tool döndür; zayıf/çelişkili → `None` (LLM'e bırak).
- **Muhafazakâr:** emin değilse `None`. Yanlış tool sabitlemek, LLM'e bırakmaktan kötü.

| Sinyal (örnek) | Tool |
|---|---|
| içeri, içeride, doluluk, boş yer, kaç araç kaldı, sahada kaç | `occupancy` |
| kaç, toplam, adet, dağılım, istatistik, yüzde, ortalama | `aggregate_events` |
| kime ait, kimin, kaç kez geldi, geçmişi, [plaka] + tekil | `vehicle_history` |
| prosedür, talimat, not, vardiya, ne yapılır, nasıl, kural | `search_notes` |
| gece giriş, overstay, 48 saat, kara liste, anomali, şüpheli, terk | `find_anomalies` |
| [tarih aralığı] + listele / hangileri / dök | `query_events` |

### B2 — `query_pipeline` entegrasyonu
- Sıra: guardrail → cache → **router** → LLM.
- Router bir tool döndürdüyse:
  - argümansız tool (`occupancy`) → **LLM'i atla**, doğrudan dispatch → anında yanıt.
  - argümanlı tool → LLM'e `tool_choice={"type":"function","function":{"name":X}}`
    ile git; model yalnızca argümanları doldurur (tool'u değiştiremez).
- Router `None` → bugünkü akış (auto + `_DOMAIN_HINTS` retry).

### B3 — sorgu normalizasyonu
- `normalize_query()`: fazla noktalama/caps/tekrar temizle
  (`"KAÇ ARAÇ İÇERİDE?!!"` → `"kaç araç içeride"`), router'a ve LLM'e girmeden.
- **6.7 hatasını doğrudan çözer.**

### B4 — `LLM_TEMPERATURE` 0.2 → 0.1
- `.env`'de şu an **0.2**. Düşürmek tool seçimini daha kararlı yapar. 1 satır.

### B5 — `demo_cache` genişletme
- 12 hazır çip + 6 senaryo promptu + yaygın varyasyonları ekle.
- Bunlar zaten **hiç LLM'e gitmemeli** → o sorular %100 deterministik.

### B6 — hedefli few-shot (`prompts.py`)
- Gözlenen her hata için 1 örnek: "içeride+caps"→occupancy,
  "kime ait + sen misin"→vehicle_history + "ben o değilim".

## Değerlendirme

| | |
|---|---|
| **Çözer** | Tutarlılık (deterministik yol %100 kararlı), gecikme (occupancy LLM atlar), maliyet (daha az çağrı), gözlenen 6.7 / 2.5 / kısmen 5.2 |
| **Çözmez** | Gerçekten muğlak sorular hâlâ modele kalır; router bakım ister |
| **Efor** | B1+B2 ~1 gün · B3/B4/B5/B6 ~yarım gün |
| **Risk** | Orta — prod sorgu hattına dokunuyor. Kötü router kuralı yanlış tool sabitleyebilir → B1 muhafazakâr + Plan A ile korunmalı |
| **Bağımlılık** | Sıfır (stdlib) |
| **Bakım** | Yeni ifade kalıpları çıktıkça router sözlüğü güncellenir |

---

## İlişki & öneri

```
A1 (baseline ölç)  →  B (uygula)  →  A1 (kanıtla: %X → %Y)
```

- **Sadece A:** ne kadar kötü olduğunu öğrenirsin, düzelmez.
- **Sadece B:** düzelir ama regresyon koruması yok; 2 hafta sonra biri
  few-shot'u siler, kimse fark etmez.
- **Minimum anlamlı adım:** `A1 + B1 + B2 + B3` → ~2 gün. Gerisi (A2/A3, B4-B6) sonra.

## Karar tablosu

| Öncelik | Seçim |
|---|---|
| "Önce ne kadar kötü olduğunu görmek istiyorum" | A1 |
| "Zaten biliyorum, direkt düzeltelim" | B1+B2+B3, sonra A1 |
| "Güvenlik tarafı beni endişelendiriyor" | A2 (redteam) + A3 |
| "Hepsini yapalım" | A1 → B (tümü) → A1 → A2/A3 |
| "En az efor, en çok kazanç" | B4 (temperature) + B5 (cache) + B3 (normalize) — yarım gün, düşük risk |
