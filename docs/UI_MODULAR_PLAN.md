# Kervansaray & Portfolyo 'Ürettiklerim' Modüler UI/UX Mimari Planı

Bu belge, **https://yagizakkaya.com.tr/urettiklerim.html** sayfasının hem **Kervansaray** projesinin canlı amiral gemisi demosu hem de gelecekteki/mevcut diğer projelerin (WebAudio/Synthesizer, Açık Kaynak CLI vb.) sergilenebileceği **modüler bir portfolyo proje vitrini** haline getirilmesi için hazırlanan kapsamlı tasarım ve uygulama planıdır.

---

## 1. Vizyon ve Problem Tanımı

### Mevcut Durum
* `urettiklerim.html`, portfolyo mimarisinde Yağız Akkaya'nın ürettiği projelerin demolarını sunduğu ortak bir vitrin olarak kurgulanmıştı.
* Kervansaray projesinin geliştirilmesi sırasında sayfanın tümü doğrudan Kervansaray'ın arayüzüne dönüşmüş, diğer projeler için alan kalmamıştır.
* Kervansaray'ı ilk kez gören ziyaretçiler (işe alım uzmanları, mühendisler, misafirler) doğrudan karmaşık teknik terimler (ALPR, Pre-flight Guardrail, SQL Tool Çağrısı, aggregate_events) ve simülatör vizörü ile karşılaşmakta; projenin hangi problemi nasıl çözdüğünü ve nasıl test edileceğini kavramakta zorlanmaktadır.

### Hedeflenen Durum
1. **Modüler Vitrin Mimarisi:** Ziyaretçilerin tek bir sayfada projeler arasında (Kervansaray, Ses Araçları, CLI) pürüzsüzce geçiş yapabildiği, URL hash (`#kervansaray`) destekli modüler bir yapı.
2. **"1 Bakışta Anla & 3 Adımda Dene" Onboarding Deneyimi:** Projeyi hiç bilmeyen birine 10 saniyede değer önerisini (Problem ➔ Çözüm) anlatan ve sistemi 3 basit adımda deneten rehberlik alanı.
3. **Çift Katmanlı Hibrit Dil:** Ana anlatım ve başlıklarda herkesin anlayacağı berrak bir Türkçe; şık rozetlerde ve İstihbarat Künyesinde ise mühendisleri etkileyecek derin teknik detaylar.

---

## 2. Mimari Kararlar (Grill-Me Mutabakatı)

| Karar Alanı | Seçilen Çözüm | Gerekçe & Avantaj |
| :--- | :--- | :--- |
| **Sayfa Mimarisi** | Tek Sayfa Entegre Vitrin (Project Switcher Tabs) | Sıfır Caddy/DNS yönlendirme riski; portfolyo global header'ı ile tam görsel uyum. |
| **Onboarding** | '1 Bakışta Anla & 3 Adımda Dene' Kahraman (Hero) Bloğu | Ziyaretçiyi teknik jargona boğmadan 10 saniyede yönlendirir ve aksiyona geçirir. |
| **Terminoloji** | Çift Katmanlı Dil (İnsan Dili + Mühendis Künyesi) | Hem teknik olmayan karar vericileri hem de kod inceleyen mühendisleri aynı anda tatmin eder. |
| **URL Yönetimi** | URL Hash Senkronizasyonu (`#kervansaray`, `#webaudio`, `#cli`) | Projelerin dışarıya doğrudan linklenebilmesini sağlar, tarayıcı geçmişini korur. |

---

## 3. Bileşen Detayları ve Uygulama Kapsamı

### A. Üst Proje Seçici Sekmesi (Modular Project Switcher)
Portfolyo ana sayfası (`#faf8fb`, zinc-900, kırmızı vurgular, JetBrains Mono fontu) ile birebir uyumlu, sayfa başlığının altına yerleşen sekme çubuğu:
- **Sekme 1: `⚡ Kervansaray (Canlı ALPR & AI Demosu)` [Aktif - Varsayılan]**
  - Tıklandığında: Kervansaray'ın tüm interaktif sistemi (Kamera Vizörü, Senaryo Kartları, Terminal, Tescil Defteri) açılır.
- **Sekme 2: `🎵 WebAudio Synth & Müzik Araçları [Deneysel]`**
  - Tıklandığında: Ses sentezleyici projesinin konsept kartı, ses motoru açıklamaları, GitHub bağlantısı ve interaktif mini önizleme/ses demosu alanı açılır.
- **Sekme 3: `🛠️ Açık Kaynak & Terminal Araçları [Geliştirici]`**
  - Tıklandığında: CLI araçları, sistem izleme betikleri ve açık kaynak depoların mimari özet kartları listelenir.

### B. Kervansaray: '1 Bakışta Anla & 3 Adımda Dene' Hero Bloğu
Kervansaray demosu başlamadan hemen önce yer alacak rehberlik bloğu:

```markdown
+-----------------------------------------------------------------------------------+
|  // 01 • AKILLI TESİS GÜVENLİĞİ & OTOPARK İSTİHBARAT MOTORU                       |
|  Kervansaray: Kamera Gözü, Veritabanı Hafızası ve Yapay Zeka Aklı                 |
|                                                                                   |
|  Problem & Çözüm:                                                                 |
|  "Geleneksel tesislerde güvenlik amirinin yüzbinlerce araç kaydı ve kamera        |
|   görüntüleri arasında arama yapması saatler sürer. Kervansaray; otomatik plaka   |
|   okuma (ALPR), SQL veritabanı ve Türkçe doğal dil yapay zekasını birleştirerek   |
|   güvenlik amirine 0.8 saniyede kesin ve doğrulanmış istihbarat sunar."          |
|                                                                                   |
|  [⚡ 0.8s Yanıt]  [🛡️ Pre-flight SQL Kalkanı]  [🧠 NVIDIA Nemotron 30B]  [🔒 Salt-Okunur DB] |
|                                                                                   |
|  --- 3 ADIMDA HEMEN DENEYİMLEYİN ----------------------------------------------- |
|  [1. Senaryo Seç]       --> [2. Kamerada İzle]        --> [3. Terminale Sor]      |
|  Aşağıdaki 6 hazır          Kamera vizöründe yapay         Doğal dil kutusuna     |
|  güvenlik senaryosundan     zekanın plakayı okuyup         aklındaki soruyu sor;  |
|  birine tıkla.              bariyer kararını anında gör.   SQL sonucunu şeffafça  |
|  (Örn: Kara Liste)                                         incele.                |
+-----------------------------------------------------------------------------------+
```

### C. Çift Katmanlı İsimlendirme ve Dil Dönüşümü (Sadeleştirme)

| Mevcut Teknik Başlık | Yeni Sadeleştirilmiş Başlık | Korunan Mühendislik Künyesi |
| :--- | :--- | :--- |
| `CANLI ALPR SİMÜLATÖRÜ` | **Canlı Kamera Akışı & Otomatik Plaka Okuma (ALPR)** | 1080p WebRTC Mock Vizör, Bounding Box |
| `DOĞAL DİL İSTİHBARAT TERMİNALİ` | **Yapay Zeka Destekli Tesis İstihbarat Terminali** | NVIDIA Nemotron 30B, Tool Calling |
| `1. MODEL ANLATISI` | **1. Asistan Yanıtı (Doğal Dil Özeti)** | Deterministik SQL Özetleyici |
| `2. SQL TOOL ÇAĞRISI` | **2. Çalıştırılan SQL Fonksiyonu** | Parametre JSON Şeması |
| `3. SONUÇ TABLOSU` | **3. Doğrulanmış Veritabanı Tablosu** | Salt-Okunur Postgres v_events |
| `MODEL GÜVENLİK & KARAR KÜNYESİ` | **İstihbarat & Karar Künyesi** | 4 Detay Kartı (Güvenlik, Zaman, Seçim, DB) |
| `ARAÇ TESCİL VE GÜVENLİK DEFTERİ` | **Araç Tescil ve Güvenlik Defteri (Hızlı Düzenleme)** | SQLite/Postgres Persistence, Alembic |
| `SON GÜVENLİK OLAYLARI AKIŞI` | **Son Güvenlik ve Geçiş Olayları Akışı** | Canlı SSE Bildirimleri, Olay Kayıtları |

---

## 4. Uygulama Adımları & Dosya Planı

1. **`src/kervansaray/api/static/index.html`:**
   - Sayfa tepesine portfolyo marka kimliğine uygun `Project Switcher (Tabs)` bileşeni entegrasyonu.
   - Kervansaray için `Hero Onboarding ("1 Bakışta Anla & 3 Adımda Dene")` kartının kodlanması.
   - Diğer projeler için (`#webaudio`, `#cli`) şık kart ve GitHub vitrin alanlarının eklenmesi.
   - Sekme geçişi ve URL Hash yönetimi için JavaScript kontrolcüsü (`switchProjectTab(tabId)`).
   - Mevcut Kervansaray modül başlıklarının ve anlatımlarının çift katmanlı dil standardına güncellenmesi.
2. **Duyarlılık ve Erişilebilirlik (Responsive & A11y):**
   - Mobil görünümde (375px - 768px) sekmelerin yatay taşmadan pürüzsüz dizilmesi.
   - 3 Adımlı rehber kartlarının mobilde dikey akışa (stacked) uyumlu hale getirilmesi.
3. **Canlı Doğrulama:**
   - Kervansaray sekmesinde tüm simülatör, terminal ve SSE fonksiyonlarının kesintisiz çalıştığının doğrulanması.
   - Diğer sekmelere geçilip geri gelindiğinde canlı sistem durumunun (state) korunması.

---

## 5. Doğrulama ve Kabul Kriterleri (Acceptance Criteria)

- [ ] **Modülerlik:** Ziyaretçi sayfayı açtığında üstte sekmeler görünür, sekmeler arası geçiş anında ve animasyonlu gerçekleşir.
- [ ] **Kervansaray Anlaşılırlığı:** Sayfayı ilk kez ziyaret eden biri, Kervansaray'ın amacını ve ne yapacağını 15 saniyede kavrar.
- [ ] **Sıfır Altyapı Etkisi:** Caddy yönlendirmesi, API endpoint'leri ve Docker servisleri kesintiye uğramadan çalışmaya devam eder.
- [ ] **Mobil Uyum:** Hem masaüstü hem cep telefonunda kusursuz grid ve okunabilir tipografi korunur.
