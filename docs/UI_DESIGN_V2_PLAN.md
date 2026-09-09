# Kervansaray Demo — Sadeleştirme & Tasarım v2 Planı

> **Bağlam:** `UI_PONYTAIL_PLAN.md` (hero + operatör butonları + ilk başlık sadeleştirme)
> uygulandı. Bu plan bir sonraki adım: **dili herkesin anlayacağı seviyeye çekmek** ve
> **sahne kurgusunu netleştirmek**, portfolyo kalitesinde şık bir tasarımla.

---

## 1. Problem

Sayfa `yagizakkaya.com.tr/urettiklerim.html` üç farklı kişiye aynı anda hitap etmeli:

| Ziyaretçi | Ne arıyor | Şu an ne oluyor |
| :--- | :--- | :--- |
| **İşe alım uzmanı / recruiter** | "Bu kişi ciddi bir şey yapmış mı?" | Etkileniyor ama derinliği göremiyor (jargon içinde kayboluyor) |
| **Mühendis** | Mimari, SQL, tool-calling, guardrail | Bunları görüyor — bu katman korunmalı |
| **Sıradan ziyaretçi / güvenlik görevlisi** | "Bu ne işe yarıyor?" | **Kayboluyor:** "İstihbarat Motoru", "Kamera Vizörü", "Nizamiye", "İstihbarat Terminali", "ALPR", "Bounding Box", "Pre-flight Guardrail" |

**Kural:** Teknik derinlik silinmez, **ikinci katmana** taşınır (küçük künye rozeti,
"Nasıl çalışıyor?" açılır kutusu, hover ipucu). Ana anlatı = mutfak Türkçesi.

---

## 2. Projeyi Bir Cümlede Anlatmak

Sayfanın en üstünde (hero), teknik hiçbir kelime olmadan:

> **Kervansaray, bir tesisin giriş kapısındaki kamerayı "gözü", araç kayıt
> defterini "hafızası" ve yapay zekayı "aklı" yapan bir güvenlik asistanıdır.**
> Kapıya gelen her aracın plakasını okur, kim olduğunu hatırlar ve güvenlik
> görevlisi Türkçe soru sorduğunda ("bu ay kaç kez geldi?", "girişi yasaklı biri
> geçti mi?") saniyeler içinde cevap verir.

Altına 3 küçük **dürüst** rozet (mühendis için): `Plaka okuma (ALPR)` ·
`Doğal dil → SQL` · `Sentetik veri · 0 gerçek kişi`.

---

## 3. Kelime Kelime Sadeleştirme

Sol sütun = ekranda büyük görünen. Sağ sütun = altına küçük gri künye / tooltip.

| Şu anki (teknik) | Yeni ana metin | Korunan künye (küçük) |
| :--- | :--- | :--- |
| `KERVANSARAY ALPR & İSTİHBARAT TERMİNALİ` | **Kervansaray — Akıllı Kapı Güvenliği** | `ALPR + Doğal Dil SQL` |
| `Kamera Vizörü` / `Vizör` | **Kapı Kamerası** | `1080p · nizamiye kamerası` |
| `Nizamiye Girişi` | **Giriş Kapısı** | — |
| `Güvenlik Operatörü` | **Güvenlik görevlisi** | — |
| `Doğal Dil İstihbarat Terminali` | **Güvenliğe Sor** | `LLM · Tool Calling · NVIDIA Nemotron` |
| `CANLI ALPR SİMÜLATÖRÜ (6 SENARYO KARTI)` | **Bir olay seç, ne olacağını gör** | — |
| `Araç / Plaka Görseli (Kamera Girişi)` | **Kameranın gördüğü** | — |
| `Plaka Sonucu (ALPR Çıktısı)` | **Sistem ne okudu?** | `OCR güven: 0.98` |
| `Bounding Box` / `ALPR OCR: 98.4%` | (etiketi kaldır — sadece yeşil çerçeve + "Plaka bulundu") | — |
| `Araç & Kişi Tescil Yönetimi` / `Tescil Defteri` | **Araç Kayıt Defteri** | `Postgres · Alembic` |
| `Eşleşme: Kayıtsız Ziyaretçi` | **Durum: Sistemde kaydı yok** | — |
| `1. Asistan Yanıtı (Özet)` | **Cevap** | — |
| `2. Çalıştırılan SQL Fonksiyonu` | **Arka planda ne yaptı?** | `tool_call + parametreler` |
| `3. Doğrulanmış Veritabanı Tablosu` | **Bu cevabın kaynağı** | `v_events · salt-okunur` |
| `İstihbarat & Karar Künyesi` | **Nasıl karar verdi?** (açılır) | 4 kart aynı kalır |
| `Pre-flight SQL Kalkanı` / `Guardrail` | künye içinde: **Zararlı komut kontrolü** | `check_query_safety` |
| `Onay Kuyruğu` (review) | **İnsan onayı bekleyenler** | — (zaten operator-only) |

> Not: künyeler `text-[10px] text-zinc-400 font-mono` — mühendis okur, diğerleri görmezden gelir.

---

## 4. Senaryo Kartları — Kurmacayı Netleştirmek

Şu an kart = rozet + isim + adres. Ziyaretçi **ne olacağını bilmeden** tıklıyor.
Her karta **bir cümlelik hikâye** + tıklayınca **ne göreceği** eklenmeli.

| Kart | Rozet | Kart üstü tek cümle (yeni) |
| :--- | :--- | :--- |
| 26 ABC 2626 | GÜVENLİK MÜDÜRÜ | "Tanıdık araç, tam yetkili — bariyer kendiliğinden açılır." |
| 06 AK 0052 | KAYITLI MİSAFİR | "Sistemde kayıtlı düzenli ziyaretçi — geçişi onaylı." |
| 34 KAY 44 | VIP | "Protokol aracı — vale ve karşılama yönlendirmesi." |
| 26 XYZ 413 | KAYITSIZ | "Sistemde kaydı olmayan kargo aracı — elle onay gerekir." |
| 06 XYZ 01 | TERK ARAÇ ŞÜPHESİ | "3 gündür tesisten çıkmayan araç — kontrol edilmeli." |
| 34 VIP 99 | KARA LİSTE | "Girişi yasaklanmış araç kapıda — sistem alarm veriyor." |

Tıklandığında kısa bir "şimdi ne oluyor" akışı (mevcut toast'lar yerine tek, sakin bir satır):
`Kamera plakayı okudu → kayıt defterinde arandı → sonuç: <durum>`.

---

## 5. Tasarım Sadeleştirme (şıklık)

1. **Tek vurgu rengi.** Şu an senaryo rozetlerinde emerald/blue/amber/sky/purple/red
   birlikte. Durum renkleri kalsın (yeşil=uygun, kırmızı=alarm, amber=dikkat), gerisi
   nötr (`zinc`). Portfolyo kırmızısı (`~#b70011`) tek aksan.
2. **Tek kart sistemi.** Aynı `rounded-2xl`, aynı `border-zinc-200/80`, aynı `shadow-sm`.
   İç bölümlerde `border-t` ile ayır, kutu içinde kutu yok.
3. **Akış sırası** (yukarıdan aşağı, hikâye gibi):
   `Hero (ne bu?)` → `Bir olay seç (kartlar)` → `Ne oldu? (kamera + sonuç yan yana)` →
   `Güvenliğe Sor (terminal)` → `Araç Kayıt Defteri`.
   Şu an kartlar kameranın *altında*; yukarı, ilk aksiyon olarak alınmalı.
4. **`font-mono` diyetine sok.** Büyük başlıklar `font-sans`; mono sadece
   künye/rozet/kod/plaka için.
5. **Mobil:** kartlar tek sütuna, dokunma hedefleri ≥44px, kamera + sonuç alt alta.
6. **Boşluk.** `gap-8` → bölümler arası nefes; hero ile ilk kart arası net ayrım.

---

## 6. Kapsam (Ponytail)

- ✅ Yalnız `src/kervansaray/api/static/index.html` (metin + sınıf değişiklikleri).
  Gerekirse `demo_cache.py` / `query_pipeline.py` narrative metinlerinde 1-2 dize.
- ✅ Senaryo verisi (`SCENARIOS` içindeki `story` alanı) eklenir — 6 satır.
- ❌ Yeni bileşen kütüphanesi, build adımı, framework yok.
- ❌ Kamera simülatörü mekaniği, SSE, terminal mantığı değişmez — sadece etiketler.
- ❌ `docs/UI_MODULAR_PLAN.md`'deki çok-projeli sekme fikri (portfolyo reposunun işi).

---

## 7. Mikro-Etkileşimler (Micro-UX Polish)

Plan koda dökülürken şu 3 ince dokunuş deneyimi zirveye taşır.

### 7.1 · Senaryo → Terminal köprüsü (bağlamsal öneri)
Bir senaryo kartına tıklandığında, kamerada olay canlanırken aşağıdaki
**"Güvenliğe Sor"** bölümündeki **o senaryoya en uygun öneri çipi** kısa süre
vurgulanır (ör. yumuşak kırmızı `ring` + tek sefer `pulse`, ~2 sn) ve görünür
alana kayar (`scrollIntoView`, yumuşak). Amaç: ziyaretçiyi doğrudan "şimdi bunu
sorabilirsin" noktasına götürmek.

- `SCENARIOS[key]` içine `chipQuery` alanı (o senaryonun eşleştiği çip metni).
- `34 VIP 99` → çip: *"Bu dönemde kara listedeki bir plaka görüldü mü?"*
- Çip zaten `#query-input`'a yazılıyordu (mevcut davranış korunur); ek olarak
  **çipin kendisi** vurgulanır. Otomatik `submitQuery()` **yok** — kullanıcı basar.

### 7.2 · Kamera başlangıç yönlendirmesi (empty state)
Sayfa ilk açıldığında **hiçbir senaryo otomatik seçilmez** (mevcut
`applyScenario(..., {silent:true})` kaldırılır). Kamera alanı sakin bir boş-durum
gösterir:

> **▲ Yukarıdan bir olay seçerek kapı simülasyonunu başlatın**
> *(hafif, yavaş yanıp sönen; ilk karta tıklanınca kaybolur)*

Bu, §5.3'teki akış sırasıyla (kartlar kameranın üstünde) tutarlı ve "hikâye"
his verir. Tescil defteri ve terminal ilk render'da varsayılan/boş halleriyle durur.

### 7.3 · Sakin süreç akışı (toast yerine)
Kart tıklamasında ekranın dört bir yanından fırlayan toast'lar yerine, kameranın
**hemen altında tek satırlık** zarif bir akış:

```
Kamera plakayı okudu  →  Kayıt defterinde doğrulandı  →  Bariyer Açıldı
```

- 3 adım sırayla belirir (~400 ms arayla, opacity/translate geçişi).
- Son adım senaryoya göre değişir: `Bariyer Açıldı` / `Giriş Engellendi (Kara Liste)` /
  `Elle Onay Bekleniyor` / `Devriye Yönlendirildi`.
- Toast'lar **yalnız** gerçek sistem bildirimleri (SSE olayları) ve hatalar için kalır.
- Yeni `#scenario-flow` elemanı; `showToast` çağrıları senaryo akışından sökülür.

---

## 8. Kabul Kriterleri

> Uygulandı: commit `00a85b9` (yalnız `src/kervansaray/api/static/index.html`, +246/−255).
> Puppeteer doğrulaması: 6 senaryo × (plaka / kırpma / akış / çip) doğru,
> 0 toast, 0 pageerror; mobil 390px yatay taşma yok; uçtan uca sorgu çalışıyor.

1. [x] **Anlaşılırlık:** Teknik olmayan biri sayfayı 20 sn okuyup "kapıdaki kamerayı
   ve kayıtları yapay zekayla birleştiren bir güvenlik sistemi" diyebilir.
2. [x] **Mühendis katmanı korunmuş:** SQL tool çağrısı, parametre JSON'u, guardrail
   künyesi, `v_events` kaynağı hâlâ görülebilir (ikinci katmanda).
3. [x] **Senaryo netliği:** Her kartın ne yapacağı tıklamadan önce belli; tıklayınca
   ilgili öneri çipi vurgulanır (§7.1).
4. [x] **Sakin geri bildirim:** Kart tıklamasında toast yağmuru yok; kameranın altında
   tek satır süreç akışı (§7.3).
5. [x] **Boş durum:** İlk açılışta kamera "olay seç" ipucu gösterir; ilk tıkla kaybolur (§7.2).
6. [x] **Görsel tutarlılık:** Tek aksan rengi, tek kart sistemi, `font-mono` yalnız
   künye/kod/plakada.
7. [x] **Sıfır regresyon:** 6 senaryo, terminal, kayıt defteri, SSE, mobil düzen
   kesintisiz.
8. [x] **Dürüstlük:** Uydurma metrik yok (bkz. `portfolio/AGENTS.md`).
