# Kervansaray — Google Stitch UI Brief

> Stitch'e yapıştırılacak proje anlatımı. İngilizce yazıldı (Stitch İngilizce
> prompt'ta daha tutarlı üretiyor); ekrandaki tüm metinler Türkçe kalmalı, bu
> yüzden UI copy'leri tırnak içinde Türkçe verildi. Canlı referans:
> https://yagizakkaya.com.tr/urettiklerim.html

---

## Prompt (kopyala-yapıştır)

```
PROJECT
Kervansaray is a portfolio demo of a "smart gate security" system for a gated site
(hotel car park, factory gate, residential compound). A fixed camera at the entrance
reads licence plates (ALPR), a Postgres registry remembers who each vehicle belongs
to, and an LLM (NVIDIA Nemotron 3.5, tool-calling → SQL) answers a security guard's
questions asked in plain Turkish. The demo runs on 100% synthetic data — no real
people, no real plates — and has a "reset demo" button.

AUDIENCE & TONE
Visitors are (1) recruiters and engineers skimming a portfolio, (2) ordinary people,
(3) a security guard with no technical background. Nobody should need to know what
"ALPR", "SQL" or "tool calling" means to enjoy the demo. Plain language first;
technical labels only as small, muted monospace captions ("künye") that engineers
can spot. Tone: calm, confident, product-grade — not a hacker terminal, not a
dashboard with 40 widgets. Turkish UI copy throughout.

BRAND / VISUAL LANGUAGE (must match the existing portfolio site)
- Fonts: "Plus Jakarta Sans" for UI text, "JetBrains Mono" for plates, badges, captions.
- Single accent colour: brand red #dc2626 (hover #b91c1c). Everything else neutral
  zinc greys. Semantic colours only to describe a gate decision:
  emerald = allowed, amber = needs attention / unknown, red = blocked.
- Light theme: page background #faf8fb with a faint dot-grid and a soft red glow at
  the top; cards are white, 16px radius (rounded-2xl), 1px zinc-200 border, soft shadow.
- Dark theme: page #0b0d12, cards zinc-900 (#18181b) with zinc-800 borders; primary
  buttons invert (light button, dark text). Both themes are required; a sun/moon
  toggle lives in the header.
- Turkish licence plate component: white plate, dark 2.5px border, blue "TR" band on
  the left, bold monospace characters, e.g. "34 VIP 99". The plate must stay white in
  dark mode (it's a physical object).
- Max content width 1152px (max-w-6xl), 24px page padding, cards stacked with 32px gaps.
  Mobile-first; on 390px everything stacks in one column with no horizontal scroll.

HEADER (sticky, translucent blur)
Left: round avatar "YA" + "Yağız Akkaya" / small mono caption "Eskişehir • ODTÜ".
Centre: pill nav with two tabs "Alanım" and "Ürettiklerim" (active, dark pill with a
pulsing red dot). Right: small mono status "Sistem Devrede" with a green ping dot, and
the theme toggle button.

PAGE STRUCTURE (top to bottom, one column of cards)

1. TITLE ROW
   Small red mono pill "// 02 • ÇALIŞMALAR // KERVANSARAY".
   H1: "Kervansaray — Akıllı Kapı Güvenliği".
   Subtitle: "Kapıya gelen aracın plakasını okur, kim olduğunu hatırlar; güvenlik
   görevlisi Türkçe sorduğunda saniyeler içinde cevaplar."
   Right side, two tiny mono chips: "● Kamera bağlı", "nemotron-3.5".

2. HERO CARD — "what is this?"
   One sentence with three bold words: "Kervansaray, bir tesisin giriş kapısındaki
   kamerayı **gözü**, araç kayıt defterini **hafızası** ve yapay zekayı **aklı** yapan
   bir güvenlik asistanıdır." Below it a lighter explanatory sentence with two quoted
   example questions. Three muted mono chips: "Plaka okuma (ALPR)",
   "Doğal dil → SQL · NVIDIA Nemotron 3.5", "Sentetik veri · 0 gerçek kişi".
   Then a 3-step strip with numbered dark squares (1, 2, 3):
   "Bir olay seç" / "Kapıda ne oluyor, gör" / "Güvenliğe sor", each with one line of help.

3. SCENARIO PICKER CARD — "Bir olay seç, ne olacağını gör"
   Caption right: "Kapıya gelebilecek 6 tipik durum".
   A 3×2 grid (1 column on mobile) of clickable scenario cards. Each card: a small
   coloured status dot + tiny status chip + the plate in bold mono on the right, and
   one plain-Turkish story sentence underneath. The six scenarios:
   - Yetkili · 26 ABC 2626 — "Tanıdık araç, tam yetkili — bariyer kendiliğinden açılır." (emerald)
   - Kayıtlı misafir · 06 AK 0052 — "Sistemde kayıtlı düzenli ziyaretçi — geçişi onaylı." (emerald)
   - VIP · 34 KAY 44 — "Protokol aracı — vale ve karşılama yönlendirmesi." (emerald)
   - Kaydı yok · 26 XYZ 413 — "Sistemde kaydı olmayan kargo aracı — elle onay gerekir." (amber)
   - Dikkat · 06 XYZ 01 — "3 gündür tesisten çıkmayan araç — kontrol edilmeli." (amber)
   - Girişi yasak · 34 VIP 99 — "Girişi yasaklanmış araç kapıda — sistem alarm veriyor." (red)
   The selected card gets a dark border and lifts slightly. Card bodies stay neutral;
   colour appears only in the dot and chip.

4. GATE ROW — two cards side by side (7/12 + 5/12), stacked on mobile
   4a. "Kameranın gördüğü" — a 4:3 black camera frame showing a night-time CCTV still
       of a car at a barrier (timestamp and "REC" burned in). Overlays: subtle vignette,
       four thin white corner brackets, a green "Plaka bulundu" bounding box over the
       plate with a red laser scan line animation when reading. Before any scenario
       is chosen the frame shows an empty-state overlay: "▲ Yukarıdan bir olay seçerek
       kapı simülasyonunu başlatın" / mono caption "kamera bekliyor".
       Under the frame a quiet one-line process flow appears step by step:
       "Kamera plakayı okudu → Kayıt defterinde arandı → Giriş engellendi" (last step
       coloured by outcome). Buttons: primary red "Plakayı tekrar oku", dark
       "Kamerayı durdur" (with green dot), outlined "Geçmişini sor →".
   4b. "Sistem ne okudu?" — mono caption "OCR güven 0.98". Label "Okunan plaka" over a
       large Turkish plate component; small caption "Tescil ili: İstanbul". Then an
       editable plate input ("Başka bir plakayı denemek için buraya yazabilirsiniz")
       with a "Kontrol et" button. Then a "Durum" box whose colour reflects the
       decision, e.g. red box: "KARA LİSTE ALARMI! Hacizli / yasaklı araç tesise
       alınamaz." with a solid red tag "GİRİŞ ENGELİ". Three small buttons:
       "Kayıt defterinde göster", "Kaydını düzenle" (emerald tint), "Bu aracı sor" (red tint).

5. REGISTRY CARD — "Araç Kayıt Defteri"
   Subtitle: "Sistemin "hafızası": kimin aracı, hangi yetkiyle giriyor. Satırları
   düzenleyip sonucun sorulara nasıl yansıdığını görebilirsiniz." + tiny mono
   "Postgres · Alembic". Right: dark button "+ Araç Kaydet / Düzenle", light button
   "Demoyu Sıfırla", and a status pill "Durum: Girişi yasak".
   Four small mono info tiles: Plaka / Sürücü / Kayıt türü / Birim-Konum.
   A 6-row table: #, Plaka Numarası, Ad Soyad, Kayıt Türü (tiny coloured badge:
   Yetkili, Kayıtlı misafir, VIP, Kaydı yok, Dikkat, Girişi yasak), Birim / Konum,
   İletişim, and a "Düzenle" button per row. Rows are clickable.

6. ASK CARD — "Güvenliğe Sor"
   Subtitle: "Aklınıza geleni Türkçe sorun. Cevabı, arka planda ne yaptığını ve o
   cevabın hangi kayıtlardan geldiğini birlikte gösterir." + tiny mono
   "LLM · Tool Calling · NVIDIA Nemotron".
   "Hazır sorular — tek tıkla, anında" with a small emerald chip "⚡ Response Cache Aktif".
   ~12 rounded question chips, e.g. "Şu an sahada kaç araç var?", "34 VIP 99 plakalı
   aracın tüm geçiş geçmişini getir.", "Bugün hava nasıl olacak? (kapsam dışı — reddeder)",
   and one rose-tinted chip "26 ABC 2626; DROP TABLE events; -- (zararlı komut — engeller)".
   A large input "Kendi sorunuzu Türkçe yazın — ör. "bugün kaç araç girdi?"" with a
   dark "Sorgula →" button.
   RESULT PANEL (appears after a question):
   - status strip: emerald pill "Cevaplandı", "Model: nemotron-3.5", "Süre: 0.001s",
     right "Anında · hazır cevap".
   - "CEVAP" card: one bold plain-Turkish sentence.
   - two columns: left a dark panel "ARKA PLANDA NE YAPTI?" (Fonksiyon: "Anomali
     taraması find_anomalies", Parametreler: JSON in green mono); right "BU CEVABIN
     KAYNAĞI" with a big number tile ("Hesaplanan Değer / Sayı" → 1) and/or a compact
     result table (Giriş, Çıkış, Plaka, Saat, İçeride).
   - collapsible accordion "NASIL KARAR VERDİ?" with an emerald badge "Temiz
     (Doğrulandı)" and caption "teknik detay"; inside, four small cards:
     "1. Güvenlik & Enjeksiyon Taraması" (KORUMALI), "2. Zaman İpucu Analizi" (ZAMAN),
     "3. Model Araç Seçimi & Karar" (TOOL), "4. Hedef Veritabanı Yüzeyi" (READ-ONLY).

7. FOOTER
   Back link "← Alanım'a (Ana Sayfa) Geri Dön", mono "kervansaray engine v1.0 • ALPR &
   Intelligence", then a slim footer bar: red mono "> terminal_ready:" "Yağız Akkaya •
   Kervansaray" and links GitHub / LinkedIn / Instagram.

MODALS
- Registry edit modal (max-w-md): blue icon, title "Araç Tescilini Düzenle: 26 XYZ 413",
  subtitle "Kaydettiğiniz bilgi anında sorulara yansır"; fields Plaka Numarası,
  Sürücü / İsim, Kayıt / Yetki Türü (select), Tahsis Birimi / Adres / Not,
  İletişim; buttons "Vazgeç" and dark "Kaydet & DB'ye Yaz".
- Toasts top-right, always dark: title row (dot + "BAŞARILI" + time + ✕) and body.

MICRO-INTERACTIONS
- Clicking a scenario: camera image swaps, laser scan sweeps, plate fills in, status
  box recolours, the matching question chip pulses with a red ring, the flow line
  reveals step by step (400ms apart). No auto-submit and no toast spam.
- Cache-hit answers appear instantly; live answers show a spinner with
  "Model çözümlüyor & SQL aracı çalıştırılıyor...".
- Keyboard focus ring: 2px brand red.

DO NOT
- No stock-photo heroes, no gradients on text, no more than one accent colour.
- Don't turn it into an ops dashboard (no KPI grids, no charts) — it is a guided demo.
- Don't invent extra scenarios or English labels; the six scenarios and the Turkish
  copy above are fixed.

DELIVERABLES
Desktop (1280) and mobile (390) screens for: empty state, blacklist scenario selected,
result panel with accordion open, registry edit modal — in both light and dark theme.
```

---

## Stitch'e verirken notlar

- Stitch tek promptta genelde 1–2 ekran üretir; önce yalnız "PROJECT + BRAND +
  HEADER + bölüm 1-4" ile masaüstü ekranını al, sonra "bölüm 5-7 + modal" için
  aynı sohbette devam et, en son "same screens in dark theme" ve "390px mobile".
- Referans görsel olarak `docs/` yerine canlı sitenin ekran görüntüsünü yükle
  (Stitch görsel referansı iyi takip eder): açık/koyu tam sayfa PNG'ler bu
  oturumun scratchpad'inde üretildi; istersen `docs/stitch/` altına koyabiliriz.
- Stitch çıktısını kod olarak alırken: Tailwind class'ları üretir ama `dark:`
  varyantlarını genelde atlar; kabul kriteri olarak "her ekran iki temada" iste.
