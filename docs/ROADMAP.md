# Kervansaray — Roadmap

`PROJECT_BRIEF.md`'deki kararları sıralı, çıkış kriterli fazlara çevirir.
Brief neyin **neden** yapıldığını söyler; bu dosya **hangi sırayla** yapılacağını.
Çelişki halinde brief kazanır — özellikle §12 (reddedilmiş yaklaşımlar).

## Kritik yol

> olay sözleşmesi → şema → ingest API → sentetik üretici → altın set →
> tool katmanı → orkestrasyon → şeffaf panel → serving → **public demo**

Nihai teslim edilebilir artefakt operatör paneli değil, **public demo**dur.
Demo bir portfolyo parçasıdır ve LinkedIn'den link'lenir; bu, geriye doğru
Faz 4 ve Faz 8'in kapsamını değiştirir (aşağıda işaretli).

## Sabit kısıtlar

Bunlar tartışmaya açık değil; her fazın tasarımını bağlar.

| Kısıt | Sonucu |
|---|---|
| **Sunucuda GPU yok** | Hiçbir model inference'ı sunucuda çalışmaz. LLM yalnızca API üzerinden çağrılır (brief §10). Görüntü hattının çıktısı **önceden render edilmiş** olarak servis edilir. |
| **Public demo açık internete maruz** | Ziyaretçilerin bir kısmı sistemi kasıtlı olarak kırmaya çalışacaktır. Abuse kontrolleri opsiyonel değil. |
| **Dataset sentetik ve sabit** | Public demo kesinlikle **read-only**. Yazma yolu, onay kuyruğu, operatör aksiyonu public yüzeyde yok. |

## Non-goals

Bilinçli olarak **inşa edilmeyecek**:

- Kimlik doğrulama / kullanıcı hesapları
- Multi-tenancy, çoklu saha
- Faz 8c'de sayılan abuse kontrolleri dışında production hardening
- Bariyer kontrolü (brief §12: v1 read-only kalır)

---

## Faz 0 — Temeller · 1 hafta

Amaç: her şeyin bağlı olduğu sözleşmeyi çivilemek.

- **Olay sözleşmesi v1.0'ı dondur**: `docs/event-contract.v1.json` (JSON Schema)
  + `src/kervansaray/events/schema.py` (Pydantic model). Brief §6'daki alanlar,
  `event_id` idempotency anahtarı, timezone'lu timestamp.
- Karar: Postgres erişimi → **SQLAlchemy 2.x + Alembic**. Şema brief §7'de
  "refine edilecek" diye işaretli; migration disiplini baştan gerekli.
- CI iskeleti: `pytest` + `ruff` + ileride altın-set runner'ını çağıracak boş
  bir `eval` job'ı.
- `pyproject`'e gerçek bağımlılıklar (sqlalchemy, alembic, psycopg, pgvector).

**Çıkış:** sözleşme dosyası + model var, `docker compose up db` çalışıyor, CI yeşil.

**Durum (2026-09-04):** ✅ `EventV1` modeli + `docs/event-contract.v1.json`
(modelden üretilir, `make schema`), 29 test, ruff temiz, CI workflow'u
(`lint-and-test` + `eval` iskelet job'ı), compose `db` servisi doğrulandı.
SQLAlchemy/Alembic kararı verildi, bağımlılıklar eklendi; Alembic init'i
Faz 1'de şema ile birlikte.

---

## Faz 1 — Track B çekirdeği: olay deposu · 2 hafta

- Brief §7 şemasını sonlandır + ilk Alembic migration (`persons`, `vehicles`,
  `registrations`, `events`, `sessions`, `notes`, `daily_summaries`).
- **`v_events`** denormalize view — tool katmanının göreceği tek yüzey.
  Ham normalize tablolar asla expose edilmez (model hatalarının çoğu join hatası).
- **Ingest API**: `POST /events` — tipli kolonlara parse, `event_id` üzerinde
  idempotency. JSONB blob'a atma; `(plate, ts)` index'leri sorguları hem hızlı
  hem doğru yapan şey.
- **Session türetme**: giriş↔çıkış eşleştirme + eksik-çıkış durumu (brief §8'in
  bir numaralı gerçek dünya problemi). "Şu an içeride kaç araç var?" sorusu bunu
  anında ortaya çıkarır.
- **Plaka reconciliation**: exact key lookup → `text/plates.py` kanoniklestirme
  → `text/fuzzy.py` bounded match → `match_status='pending'` insan onay kuyruğu
  (brief §3.8). Edit distance 1 asla otomatik kabul edilmez.

**Çıkış:** elle atılan bir JSON olay akışı DB'ye doğru düşüyor, tekrarlar
reddediliyor, session'lar oluşuyor.

**Durum (2026-09-04):** ✅ ana iş bitti.
- `src/kervansaray/db/models.py` — 7 tablo (§7). `sessions` üç biçim:
  normal / `missing_exit` / `missing_entry` (§8). `events.candidate_vehicle_id`
  §7'ye ek (pending review kuyruğu için).
- `alembic/` + `0001_initial_schema` — pgvector extension + `create_all` +
  `v_events` view. `test_migrations` upgrade→downgrade→upgrade doğruluyor.
- `src/kervansaray/ingest/` — `reconcile_plate` (exact → bounded fuzzy, edit
  distance 1 **pending**, il-kodu ile aday havuzu daraltma), `apply_event`
  (session türetme), `ingest_event` (idempotency + tek transaction).
- `src/kervansaray/api/` — `POST /events` (422 sözleşme hatası, 200 duplicate,
  201 yeni), `GET /events` (yalnız `v_events`, satır tavanı 200), `/healthz`.
  `wsgi.py` gunicorn girişi.
- Testler: `test_reconcile`, `test_ingest` (Faz 1 çıkış kriterleri),
  `test_api`, `test_migrations` — CI'da `services.postgres` (pgvector) ile.
- **Kalan (Faz 2'ye taşındı):** çok sırasız (`exit < entry`) olayların tam
  mutabakatı; sentetik üretici o senaryoyu üretince ele alınacak.

---

## Faz 2 — Sentetik olay üreticisi · 1.5 hafta

- ~200 araç: kayıtlı misafir, personel, tedarikçi, bilinmeyen.
- Gerçekçi ritim: 14:00–18:00 check-in piki, sabah checkout, vardiya
  desenleri, hafta içi/hafta sonu farkı.
- **Bilerek kir enjekte et** (brief §8): eksik çıkış olayları,
  store-and-forward tekrarları, tek karakter bozuk plakalar, sırasız gelişler,
  saat kayması.
- Enjekte edilen anomaliler: üç gün kalan araç, beş gece üst üste gelen
  kayıtsız araç, 03:00 girişi, kara listedeki plaka.
- Dummy plaka konvansiyonu: kütle veri gerçek il kodlarıyla (01–81) üretilir ki
  gerçek doğrulama yolundan geçsin; **82–99** yalnızca kesin-sentetik ve
  geçersiz-il ret yolunu test etmek için ayrılır.
- Üretici çıktıyı **ingest API üzerinden** yükler (kendi API'ni dogfood et).

**Çıkış:** aylarca olay üretilip yüklenebiliyor; ground truth script'le biliniyor.

---

## Faz 3 — Altın set + eval harness · 1 hafta

Downstream'in tamamını kilitler. Sistem "chatbot çalışıyor gibi" seviyesinde
teslim edilebilir değil (brief §9).

- ~50 soru: `soru / beklenen tool çağrısı / beklenen cevap`.
- Cevaplar sentetik DB'ye karşı **script'le hesaplanır** — sentetik başlamanın
  asıl metodolojik kazancı budur, elle etiketleme yok.
- Soru dağılımı gerçekçi olsun: sayısal/zamansal, sıralama, "şu an içeride",
  fuzzy-zamansal, serbest metin.
- Runner doğruluk oranı raporlar; CI'a bağlanır. Her prompt veya tool-şeması
  değişikliğinde çalışır.

**Çıkış:** `make eval` bir sayı basıyor. Bu sayı artık ilerlemenin tek ölçüsü.

---

## Faz 4 — Tool katmanı · 2 hafta

- 5 tipli tool (brief §3.2): `query_events`, `aggregate_events`,
  `vehicle_history`, `find_anomalies`, `search_notes`.
- **Modelden önce, deterministik Türkçe çözümleme** (brief §3.5):
  "dün gece / geçen hafta / bu ay / hafta sonu" → kod içinde mutlak aralığa
  çevrilir; plaka normalizasyonu lookup öncesi yapılır. Modele tarih aritmetiği
  yaptırma — sessiz hata üretir.
- Prompt'a: semantic view + açık sözlük (enum değerleri: `direction`,
  `match_status`, il kodu aralığı) + 10–15 few-shot örneği.

### Guardrail'ler — hepsi bu fazda, sonradan eklenmez

Bunların bir kısmı yalnızca public demo için gerekli görünebilir; **değil**.
Faz 8c'de bolt-on olarak eklenmeleri hem kod hem prompt tarafında yeniden
yazım demektir. Baştan guardrail setinin parçasıdırlar:

- Read-only DB kullanıcısı — query katmanının dokunduğu her şey için.
- ~50 satır tavanı; üstünde aggregate çağrısına zorla. Model yapısal olarak
  "gözle sayamamalı" (brief §3.3).
- Her sonuçta provenance: tool çağrısı + arkasındaki event ID'leri.
- **Kapsam sınırlayıcı system prompt**: yalnızca otopark/araç verisi. Kapsam
  dışı sorular reddedilir, ve bunun **testi altın setin parçası olur**.
- **Yanıt başına max token tavanı.**

**Çıkış:** her tool tek tek unit-test'li; altın setteki "beklenen tool çağrısı"
alanı doğrulanabiliyor; kapsam dışı sorular testte reddediliyor.

---

## Faz 5 — LLM sorgu orkestrasyonu · 1.5 hafta

- Router 3 yol (brief §3.6): relational (sayısal/zamansal/kesin), vector
  (semantik/serbest metin), daily summary (fuzzy zamansal).
- **Kendini düzelten döngü** (brief §3.4): tool çağrısı hata verir veya sıfır
  satır dönerse hata modele geri beslenir, 2–3 denemeyle sınırlı retry.
  Sistemin savunulabilir şekilde *agentic* olduğu nokta burasıdır.
- Şema + few-shot için prompt caching (tekrarlayan maliyetin çoğunu siler).
- Altın seti çalıştır, hedef doğruluğa iterasyon.

### Karar noktası: birincil LLM sağlayıcısı — ölçümle çözülür

Birincil sağlayıcı **baştan sabitlenmez**. Faz 3 altın seti her aday sağlayıcıya
(groq / gemini / openai) karşı ayrı ayrı çalıştırılır ve seçim **ölçülen
tool-calling doğruluğuna** göre yapılır. `LLM_PROVIDER_ORDER` bu ölçümün
çıktısıdır, itibarın veya varsayımın değil. Ölçüm sonucu ve tarihi bu dosyaya
not düşülür.

**Çıkış:** altın set doğruluğu hedefte; sağlayıcı sırası ölçüme dayanarak
sabitlenmiş.

---

## Faz 6 — Gerçek RAG'in yeri · 1 hafta

Vektör retrieval yalnızca iki yerde, ikisi de serbest metin (brief §3.6).
Ham olay satırları üzerinde naive RAG **yok** (brief §12).

- Aynı Postgres içinde **pgvector** — ikinci servis yok (brief §10).
- `notes` tablosu + embedding'ler (gece CPU batch; sunucuda GPU yok).
- **Gece günlük-özet üreticisi**: her günün prose özeti üretilip embed edilir.
  Fuzzy-zamansal sorular ("geçen ay ne zaman anormallik vardı?") ancak bu
  sayede retrievable olur — embed edilen şeyi değiştirme numarası.
  Bu aynı zamanda brief §11'deki otonom gece araştırmacısının tohumudur.
- `search_notes` gerçek vektör retrieval'a bağlanır.

**Çıkış:** fuzzy-zamansal altın-set soruları geçiyor.

---

## Faz 7 — Bildirimler · 1 hafta

- Her gelen olayı değerlendiren **deterministik kural motoru** (brief §3.7).
  LLM asla tetikleyici değildir — yalnızca mesaj metnini yazar. Latency, maliyet
  ve non-determinizm bunu diskalifiye eder.
- Kurallar: kayıtsız araç, kara liste eşleşmesi, overstay, bilinen misafir
  geliyor.
- Operatör masaüstüne WebSocket push.

**Çıkış:** sentetik akışta enjekte edilen anomaliler doğru bildirimi tetikliyor.

---

## Faz 8 — Operatör paneli · 1.5 hafta

### Her cevap üç şeyi birden gösterir — ilk günden

Bu bir retrofit değildir. Düz bir chat paneli yazıp şeffaflığı sonradan eklemek
hem panelin bilgi mimarisini hem de demo'nun ikna ediciliğini bozar.
Her yanıtta yan yana:

1. **Modelin prose'u** — kolaylık.
2. **Tool çağrısı + parametreleri** — ne sorulduğu.
3. **Sonuç tablosu** — gerçek. Anlatı değil, tablo doğrudur (brief §3.3).

Bu hem correctness garantisidir hem de demo'daki en inandırıcı tek unsurdur.

Panelin geri kalanı:

- Provenance görünümü (event ID'lerine kadar).
- `pending` plaka eşleşmeleri için onay kuyruğu — sistemin birincil güven
  mekanizması; düzeltmeler aynı zamanda eğitim verisi olur.
- Bildirim akışı.

**Çıkış:** sentetik veriyle çalışan, üç görünümlü panel.

---

## Faz 8b — Serving layer · 0.5 hafta

Demo'nun üstünde duracağı zemin.

- Postgres, tool API ve panel **tek host** üzerinde, önünde **Caddy** ile gerçek
  bir domain'de otomatik TLS.
- Postgres yalnızca **localhost**'a bind edilir. Tek public yüzey HTTPS API'dir.
- Query katmanının dokunduğu her şey için **read-only DB kullanıcısı**
  (Faz 4'te tanımlanan kullanıcı burada gerçek deployment'ta uygulanır).
- Secrets env üzerinden. **LLM API anahtarı yalnızca sunucuda bulunur** —
  repoda, istemcide veya build artefaktında değil.
- **Günlük otomatik Postgres dump** → host dışı depolamaya.
- Sunucuda GPU yok; hiçbir serviste model inference'ı çalışmaz.

**Çıkış:** temiz bir checkout'tan `docker compose up` stack'i sunucuda
yeniden üretiyor.

---

## Faz 8c — Public demo arayüzü · 1 hafta

**Bu, Faz 8 operatör paneli değildir.** Onun sertleştirilmiş, read-only,
küratörlü bir alt kümesidir: onay kuyruğu yok, yazma yolu yok, operatör
aksiyonu yok.

### Etkileşim

- **8–10 önerilen soru, tıklanabilir chip olarak** = birincil etkileşim.
  Ziyaretçi ne soracağını bilmek zorunda kalmamalı.
- Serbest metin kutusu vardır ama **ikincildir**.
- Her cevap Faz 8'deki üç görünümü aynen taşır: prose + tool çağrısı + tablo.

### Dashboard tarafı

- Son olaylar akışı.
- Anlık doluluk.
- Bir plaka crop'u.
- Sentetik bir olay üzerinde tetiklenen kural motoru uyarısı — sistemin
  yalnızca soru cevaplamadığını gösterir.
- Görüntü hattı için **önceden render edilmiş annotated klip**. Sunucuda
  inference yok, olamaz.

### Abuse kontrolleri — public'e çıkmadan önce hepsi zorunlu

- Query endpoint'inde **IP başına rate limit**.
- LLM API anahtarında **sert aylık harcama tavanı**.
- **Yanıt başına max token** (Faz 4'ten gelir).
- **Kapsam sınırlayıcı system prompt** (Faz 4'ten gelir): otopark verisi dışı
  sorular reddedilir, ve bunun testi vardır. Ziyaretçilerin deneyeceği **ilk
  şey** budur; tesadüfe bırakılamaz.

**Çıkış:** tanımadığın biri URL'yi açıyor, önerilen bir soruya tıklıyor ve
cevabı, tool çağrısını ve sonuç tablosunu görüyor.

---

## Faz 10 — Track A: görüntü hattı

Panel demo'su ayakta olduktan **sonra** başlar. Brief §2: Track B'de gerçek
belirsizlik var, ALPR ise çözülmüş bir problem.

- Geliştirme hedefi yerel RTX 4070. Jetson yalnızca deployment hedefi (brief §5).
- Hat: frame → araç tespiti (YOLO) → ByteTrack → plaka tespiti → plaka OCR →
  **gramer-kısıtlı decoding** + **çok-kare confidence-weighted voting** →
  sanal çizgi geçişi → yön → **track başına tek olay** (frame başına değil).
- Aynı brief §6 sözleşmesini üretir; Track B'ye drop-in takılır.
- Kamera modelden önemlidir (brief §4.2): IR illuminator + IR-pass filtre,
  kısa pozlama, <30° montaj açısı.
- INT8 doğruluk kaybı ölçümü 4070'te yapılır (donanımdan bağımsızdır);
  yayınlanmış Jetson FPS'leriyle birleştirilip board satın alınmadan seçilir.
- Demo için çıktı **önceden render edilir** — sunucuda GPU yok.

Staj süresi yeterli değilse bu faz tamamen düşürülebilir; Faz 8c tek başına
teslim edilebilir bir sonuçtur.

---

## Faz 11 — Hardening: neyin kapsamda olduğu

Roadmap'te iki farklı şey "hardening" diye anılıyordu; ayrımı net tutmak gerekir.

### Kapsam içi — zorunlu, Faz 8c'de teslim edilir

Public demo açık internete maruz olduğu için bunlar ertelenemez:

- Query endpoint'inde IP başına rate limit
- LLM API anahtarında aylık harcama tavanı
- Yanıt başına max token
- Kapsam sınırlayıcı system prompt + testi
- Postgres'in yalnızca localhost'a bind edilmesi, read-only DB kullanıcısı
- Günlük yedek

### Kapsam dışı — veri sentetik olduğu sürece

- KVKK uyum çalışması
- Alan/kolon şifrelemesi
- Retention politikası
- Pseudonymisation

Gerekçe brief §14: ortada gerçek kişisel veri yok. Bunlar **bir kamera gerçek
bir otoparka bakar bakmaz** geri döner. Brief §7'deki tablo ayrımı (kişi ve
plaka verisinin kendi tablolarında, `events`'ten ID ile referanslanması) tam da
bunu migration kabusu olmaktan çıkaran ucuz dikiştir — o yüzden ayrım şimdiden
korunur.

---

## Sıralama notları

- **Faz 1–4 LLM'e sıfır bağımlıdır.** Brief §15 bunu vurguluyor: bu dört faz
  sonrasının şeklini belirler ve hiçbir model kararı beklemez.
- **Faz 3 bir kapıdır.** Altın set olmadan Faz 5'teki iterasyon ölçülemez,
  Faz 5'in sağlayıcı kararı verilemez.
- Faz 8'in üç-görünüm kuralı ile Faz 4'ün guardrail'leri, Faz 8c'nin geriye
  yaydığı iki gereksinimdir. İkisi de sonradan eklenirse yeniden yazım demektir.
- Kabaca **14–16 hafta** tek kişi, Faz 10 hariç.

## Açık karar noktaları

| Karar | Nasıl çözülecek | Ne zaman |
|---|---|---|
| ORM | SQLAlchemy 2.x + Alembic (öneri) | Faz 0 |
| Birincil LLM sağlayıcısı | Altın set ölçümü, itibar değil | Faz 5 |
| `find_anomalies` kurallarının yeri | Faz 7 kural motoruyla ortak mı, ayrı mı | Faz 4–7 arası |
| Demo domain'i | — | Faz 8b |
