# Kervansaray

Sabit kameralarla otopark giris/cikis zekasi: plaka -> yapilandirilmis olay
-> depolama -> dogal dil sorgu arayuzu + kural tabanli masaustu bildirimleri.

> Tam proje baglami, kararlar ve **reddedilmis yaklasimlar** icin:
> [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md). Reddedilenler bolumu (S12)
> opsiyonel okuma degil.
>
> Sirali plan, cikis kriterleri ve acik karar noktalari icin:
> [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Durum

Ogrenci/staj projesi, **sadece sentetik veri**. Kamera yok, gercek kisisel
veri yok. Su an repoda yalnizca CILEKAI'dan tasinan operasyonel iskelet var;
projeye ozel parcalar (sema, ingest API, sentetik uretici, tool katmani,
altin set) `docs/ROADMAP.md` sirasina gore yazilacak.

Nihai teslim edilebilir artefakt, sentetik veriyle calisan **public demo**dur
(ROADMAP Faz 8c): read-only, kuratorlu, her cevapta modelin prose'u + tool
cagrisi + sonuc tablosu birlikte gosterilir.

## Dizin yapisi

```
kervansaray/
  docs/PROJECT_BRIEF.md         proje sozlesmesi / handoff dokumani
  docker-compose.yml            iskelet: app + Postgres(pgvector)
  Dockerfile
  requirements.txt
  .env.example                  -> kopyala .env yap, doldur
  src/kervansaray/
    config.py                   pydantic-settings (CILEKAI deseni)
    logging.py                  yapilandirilmis konsol + dosya logu
    observability.py            Prometheus metrikleri + Flask entegrasyonu
    llm/
      __init__.py               saglayici fallback zinciri
      groq_client.py
      gemini_client.py
      openai_client.py
    text/
      turkish.py                turkish_lower + normalizasyon
      plates.py                 Turk plakasi kanoniklestirme/dogrulama (S4.1)
      fuzzy.py                  bounded fuzzy match; edit-distance 1 asla oto-kabul (S3.8)
```

## CILEKAI'dan tasinanlar (ve neden)

`PROJECT_BRIEF.md` S13'e gore CILEKAI bir **referans**, bagimlilik degil.
Dosya dosya, bilincli sekilde kopyalandi:

| Tasinan | Kaynak | Not |
|---|---|---|
| LLM istemcileri + fallback zinciri | `infra/llm/*` | groq/gemini/openai; yerel (ollama, anythingllm) haric (S10) |
| Docker Compose iskeleti | `docker-compose.yml` | ollama/anythingllm/qdrant cikarildi; pgvector eklendi |
| config deseni | `core/config.py` | yapı tasindi, RAG/embedding ayarlari tasinmadi |
| logging | `core/logging.py` | cekirdek korundu, pipeline metodlari alana uyarlandi |
| gozlemlenebilirlik | `main.py` Prometheus blogu | RAG metrikleri -> olay/tool/LLM/bildirim metrikleri |
| Turkce normalizasyon | `core/faq_manager.py` `turkish_lower()` | birebir |
| fuzzy eslestirme | `core/faq_manager.py` rapidfuzz | S3.8 kurali kodlandi |

**Tasinmayanlar:** tum retrieval yigini (BM25 + RRF + reranker + FAISS/Qdrant
+ semantic cache). Gerekce `PROJECT_BRIEF.md` S12.

## Gelistirme

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e .
cp .env.example .env    # degerleri doldur
```

```bash
docker compose up -d db      # Postgres + pgvector
```
