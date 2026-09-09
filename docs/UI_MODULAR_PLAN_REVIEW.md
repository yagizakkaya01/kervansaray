# UI_MODULAR_PLAN — Boşluk Analizi

> [`docs/UI_MODULAR_PLAN.md`](UI_MODULAR_PLAN.md) (commit `1addfb1`) incelemesi.
> Plan iyi bir üst-seviye vizyon ama uygulanabilir bir spec değil; aşağıdaki
> boşluklar kapatılmadan koda başlanmamalı. En büyükten küçüğe.

---

## A. Mimari boşluklar (blocker)

### A1 · Sayfa kimin? — çözülmemiş çelişki
Plan "portfolyo vitrini" diyor ama sayfa **%100 `kervansaray_app`** tarafından
servis ediliyor:
`Caddy: /urettiklerim.html → rewrite * / → kervansaray_app:8000`.
Portfolyonun kendi `~/portfolio/public/urettiklerim.html`'i şu an **ölü** (Caddy gölgeliyor).

Plan "`src/kervansaray/api/static/index.html`'i düzenle" diyor → sonuç:
- WebAudio Synth + CLI içeriği **Kervansaray Flask app'inin static klasöründe** yaşar (tuhaf bağımlılık)
- Her portfolyo içerik değişikliği bir **Kervansaray deploy'u** gerektirir
- Eşleşmesi istenen "portfolyo global header'ı" `portfolio/public/index.html`'de
  tanımlı → Kervansaray içinde yeniden yazılıp **iki kopya** olur, kayarlar

**Karar gerekli (plan hiçbirini seçmiyor):**
- (a) Vitrin portfolyoya taşınır, Kervansaray iframe/proxy ile gömülür
- (b) `/urettiklerim.html` portfolyoya route edilir, portfolyo Kervansaray demosunu embed eder
- (c) "Kervansaray sahibi" kabul edilir ve gerekçesi yazılır

### A2 · "Modüler" aslında modüler değil
Plandaki modülerlik = tek dev HTML dosyasında sekmeler. Component ayrımı, build,
ayrı JS modülü yok. 3 ayrı interaktif demo (Kervansaray SSE terminali + WebAudio
audio graph + CLI kartları) tek `<script>` bloğunda → isim çakışması, bir syntax
hatası hepsini öldürür, izole test imkânsız. `index.html` zaten 2134 satır; plan
3000+ yapar.
**Gerçek modülerlik:** iframe-per-proje | `<script type="module">` per proje | küçük build adımı.

### A3 · Sekmeler arası state — kriter var, tasarım yok
"Sekmeye geri gelindiğinde canlı durum korunmalı" bir kabul kriteri ama **nasıl** yok.
Kervansaray'da: açık SSE (`/api/notifications/stream`), çalışan HUD clock interval'ı,
seçili senaryo, kamera aç/kapa, sorgu paneli. WebAudio sekmesine geçince:
- SSE açık mı kalıyor (sızıntı) yoksa reconnect fırtınası mı?
- `AudioContext` eager mi? (tarayıcı user-gesture ister, gizli sekmede suspend eder)

**Gerekli:** sekme yaşam döngüsü hook'ları (`onEnter`/`onLeave`), SSE pause/resume,
`AudioContext` lazy-init.

---

## B. Eksik spec'ler (uygulama öncesi)

### B1 · Güvenlik durumu hiç geçmiyor
Plan "Tescil Defteri (Hızlı Düzenleme)" + "Düzenle" butonlarını öne çıkarıyor — ama
`POST /api/registry/upsert` artık `@operator_only` → **her ziyaretçide 403**.
Aynı şekilde "Demo Reset" (403), "Kota Sıfırla" (404). Plan public'te bu kontrollerin
**gizli mi / disabled+tooltip mi** gösterileceğini belirtmeli. Şu an "Düzenle"'ye
basan recruiter kırık bir şey görüyor. (bkz. [`ERROR.md`](../ERROR.md))

### B2 · Performans / sayfa ağırlığı
- `cdn.tailwindcss.com` = ~3 MB dev-only JS; production'da olmamalı (zaten sorun,
  plan büyütüyor). Build'lenmiş CSS gerekli.
- 6 webp (~800 KB) sadece Kervansaray sekmesi aktifken (`loading="lazy"` + tab-gated).
- WebAudio motoru / diğer sekme içerikleri lazy.
- Tek dosya → bir hata = tüm vitrin çöker.

### B3 · Erişilebilirlik — tek satır
"A11y" sadece "mobilde sekme taşması" olarak geçiyor. Eksik:
- Sekmeler: `role="tablist"/"tab"`, `aria-selected`, ok tuşu navigasyonu
- Canlı terminal / olay akışı: `aria-live`
- Kamera simülatörü tamamen görsel — ALPR'nin "gördüğü" için metin alternatifi yok
- Renk-only durum (kara liste = kırmızı) → metin etiketi
- Sekme geçişinde focus yönetimi

Recruiter'a yönelik portfolyoda a11y bir sinyal.

### B4 · SEO / meta / paylaşım
- `rewrite * /` → URL `/urettiklerim.html`, içerik `/`. `#webaudio` deep-link →
  önce tüm sayfa yükleniyor sonra JS geçiş yapıyor.
- Sekme başına `<title>` yok, **Open Graph tag'i yok** — ROADMAP "LinkedIn'den
  linklenir" diyor; recruiter linki paylaşınca önizleme boş.

### B5 · Rollback / paralel geliştirme
Canlı çalışan bir sayfanın **büyük** rewrite'ı. İki kişi (Claude + Gemini)
`index.html`'i düzenliyor → 2134 satıra 800 satır ekleme = merge cehennemi.
Plan sıralama vermeli: **önce** mevcut Kervansaray bloğunu stabil bir parçaya çıkar,
**sonra** sekme kabuğunu ekle. Feature-flag / branch stratejisi yok.

### B6 · Test
"Canlı Doğrulama" = elle kontrol. Otomatik yok. En az bir puppeteer smoke:
her sekme yükleniyor, geçiş + hash sync çalışıyor, Kervansaray SSE geri dönünce
reconnect oluyor. (ERROR.md E1: yeni yüzeyin zaten sıfır testi var.)

---

## C. İçerik / dürüstlük sorunları

### C1 · Hero'daki "0.8s Yanıt" uydurma
Gerçek: kuratorlu cache = **0 ms** (16 soru), canlı LLM = **4–30 sn** (nemotron,
değişken). `portfolio/AGENTS.md` sabit kuralı: **"Sahte/uydurma veri yok."**
Rozet → "0 ms (önbellek) / ~5 sn (canlı model)".

### C2 · "yüzbinlerce araç kaydı"
Problem tanımındaki "yüzbinlerce araç kaydı" — demo DB'de **~220 event**. Anlatı
gerçekçi ölçekte olmalı ya da "gerçek tesiste yüzbinlerce" diye çerçevelenmeli.

### C3 · WebAudio / CLI projeleri var mı?
Plan bunları varmış gibi anıyor. Yoksa → boş sekmeler için altyapı kuruluyor.
`AGENTS.md`: "Yapım Aşamasında" göstermek OK ama dürüstçe: Kervansaray tek gerçek
içerik, sekme 2-3 stub. "Ses demosu" için `AGENTS.md` telifli medya yasağı geçerli.

### C4 · Çift-katmanlı dil eşlemesini kim senkronda tutacak?
Terminoloji tablosu (bölüm C) statik doc. Gerçek string'ler `index.html` +
`demo_cache.py` + `query_pipeline.py` (narrative'ler) + `build_audit_metadata`
(label'lar) içinde — bazıları **server-side üretiliyor**. Plan "doc ↔ kod senkronu"
demiyor.

---

## D. Süreç / organizasyon

### D1 · Yanlış repo
Plan `kervansaray/docs/`'ta ama **portfolyo işi** anlatıyor. PROJECT_BRIEF:
Kervansaray'ın teslim edilebiliri "kuratorlu read-only demo". 3-proje vitrin
switcher'ı Kervansaray roadmap'inden scope drift.

### D2 · Ölçüm yok
"3 adımda dene" funnel'ında sıfır enstrümantasyon. Portfolyoda `/api/stats` sayaç
var; en azından client-side funnel counter.

---

## Öncelik

| Boşluk | Etki |
|---|---|
| A1 sayfa sahipliği | **Blocker** — karar verilmeden kod yazılırsa yanlış yere yazılır |
| A2 modülerlik | Yüksek — bakımı imkânsız tek dosya |
| A3 sekme state / SSE | Yüksek — bağlantı sızıntısı / reconnect fırtınası |
| B1 403 butonları | Orta — recruiter kırık UI görüyor |
| B2 Tailwind CDN / ağırlık | Orta |
| C1 "0.8s" uydurma | Orta — AGENTS.md ihlali |
| B3 a11y · B4 OG tag · B5 sıralama · B6 test | Orta |

**Öneri:** Plan v2'de önce A1 (mimari), sonra A2–A3 (modülerlik + yaşam döngüsü)
netleşsin; hero metni gerçek sayılarla düzelsin; uygulama sırası "önce mevcut
demoyu izole et" ile başlasın.
