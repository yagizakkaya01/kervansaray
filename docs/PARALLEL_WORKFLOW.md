# Paralel Geliştirme Protokolü — Claude Code + Antigravity

> İki ajan aynı repoda paralel çalışıyor. Bu dosya: iş bölümü, çakışma
> önleme ve token disiplini. Her iki ajan da oturum başında okur.
>
> - **Claude Code** → model: **Claude Sonnet 5** (`claude-sonnet-5`)
> - **Antigravity** → model: **Gemini 3.8 Flash (high)** (`gemini-3.8-flash`)
>
> Canlı durum panosu: `docs/PARALLEL_STATUS.md`. Tarih: 2026-09-10.

---

## 1. Model profilleri (Eylül 2026 kıyas verisi)

| | Sonnet 5 (Claude Code) | Gemini 3.8 Flash high (Antigravity) |
|---|---|---|
| Fiyat (1M tok) | $2 giriş / $10 çıkış | **$0.75 / $3.75** (~4× ucuz) |
| Hız (throughput) | ~69 t/s | **~340 t/s** (~5× hızlı), TTFT 0.7s |
| Context / max çıktı | 1M / **128K** | 1M / 64K |
| SWE-bench Pro | **63.2%** | 61.6% |
| Terminal-Bench 2.1 | 80.4% | **90.8%** |
| Bilgisayar/tarayıcı kullanımı | **güçlü** (OSWorld 81, BrowseComp 85) | zayıf |
| Deep SWE v1.1 | — | 73.7% (Opus 5 seviyesi) |

**Dürüst okuma:** Çekirdek kodlamada ikisi başa baş (SWE-bench Pro farkı 1.6
puan → gürültü). Gerçek ayrım **maliyet/hız** ve **yetenek kenarları**:
Gemini terminal/tool-döngüsünde ve ucuz-hızlı yığın işte; Sonnet
tarayıcı/bilgisayar kullanımında, web araştırmasında ve en zor repo
görevlerinde. Görevi benchmark puanına göre değil **yapısal uyuma** göre dağıt.

---

## 2. İş bölümü

### Gemini 3.8 Flash (Antigravity) — ucuz, hızlı, terminal-güçlü
- Yığın mekanik değişiklik: N dosyada yeniden adlandırma, kalıp uygulama, boilerplate
- Kesinleşmiş plandan iskele kurma (ör. `TOOL_PARAMETER_EXPANSION_PLAN.md` → kod)
- Alembic migration, `scripts/`, `synth/` sentetik veri
- Şekli kararlaştırılmış test yazımı
- Çıktıyı izleyerek hızlı yineleme döngüleri
- `src/kervansaray/api/` route, `db/` tesisatı

### Claude Sonnet 5 (Claude Code) — tarayıcı, araştırma, muhakeme, kesişen işler
- Canlı site doğrulaması (puppeteer — mevcut kalıp)
- Web araştırması (benchmark, kütüphane/API bilgisi, doküman)
- Mimari/tasarım kararı, ödünleşim analizi, plan yazımı
- Güvenlik incelemesi, guardrail/injection muhakemesi, LLM pipeline & prompt işi
- Zor/ince hata ayıklama
- Bütün sistemi akılda tutmayı gerektiren kesişen refactor'lar
- Caddy / altyapı / deploy (`~/portfolio/`)

### İkisi de (kimde context varsa)
- Küçük lokal hata düzeltmeleri
- Tek dosyalık feature'lar
- Kendi kulvarındaki doküman güncellemesi

---

## 3. Kulvar haritası (yumuşak — kulvar dışına çıkacaksan önce STATUS'a yaz)

| Kulvar | Sahip |
|---|---|
| `docs/` (planlama), `src/kervansaray/llm/`, `query_pipeline.py`, `tools/` mantığı, `demo_cache.py`, güvenlik, `~/portfolio/` | **Claude** |
| `src/kervansaray/api/` route, `src/kervansaray/db/`, `alembic/`, `scripts/`, `src/kervansaray/synth/`, `tests/` | **Gemini** |
| `api/static/index.html`, `prompts.py`, `schemas.py`, `.env`, `docker-compose.yml` | **PAYLAŞIMLI** — dokunmadan önce STATUS'a "WIP" yaz |

---

## 4. Koordinasyon kuralları

1. **Oturum başı:** `git fetch && git status && git log --oneline origin/main -5`, sonra `PARALLEL_STATUS.md` oku.
2. **İşi sahiplen:** `PARALLEL_STATUS.md`'de kendi bölümünü güncelle, **önce onu commit et** (`docs: claim <görev>`). Diğer ajan bu satırı görünce o alana girmez.
3. **Küçük commit, hemen push.** Yerelde commit biriktirme — diğer ajan göremez.
4. **Mesaj öneki:** `feat(scope):` / `fix(scope):` / `docs:` · scope = ui/api/llm/db/tools/infra.
5. `main`'e asla force-push yok, paylaşılan geçmişe asla rebase yok.
6. **Push reddedilirse:** sen `git rebase origin/main` yap, çöz, tekrar push et.
7. **Paylaşımlı dosya çakışması:** sahibi olmayan geri çekilir, sahip önce iner.
8. Diğerinin işini **kullanıcı istemedikçe** tekrar inceleme / tekrar test etme.
9. Diğeri commit attıktan sonra **tüm dosyayı değil** `git show <sha>` oku.
10. "Testler geçti" beyanına güven; o alana dokunmuyorsan tekrar çalıştırma.

---

## 5. Token disiplini (iki taraf da)

- Context şurada yaşıyor: `PARALLEL_STATUS.md` + `docs/*_PLAN.md` + `PROJECT_BRIEF.md`. Bunları oku, yeniden keşfe çıkma.
- Tam dosya okuması yerine `git show` / `git diff`.
- İlgili değişiklikleri tek oturumda topla, çok sayıda küçük oturuma bölme.
- Plan dosyalarını güncel tut → hiçbir ajan aynı analizi ikinci kez yapmasın.
- Kullanıcının "diğer ajan bitirdi" demesini bekle; tahmin yürütüp iş çakıştırma.

---

## 6. Kullanıcıdan gelen devir sinyalleri

| Sinyal | Ne yaparım |
|---|---|
| "X bitti, sıra sende" | `git fetch` → STATUS oku → plandaki yerden devam |
| "bunu Gemini'ye/Claude'a bırak" | STATUS'a 3 satırlık spec yaz, dur |
| "ikiniz de bakın" | Kulvarını al, STATUS'ta parçanı işaretle, paralel git |
