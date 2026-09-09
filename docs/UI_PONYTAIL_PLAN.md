# Kervansaray UI/UX: Ponytail Sadeleştirme & Onboarding Planı

> **Bağlam:** [`UI_MODULAR_PLAN.md`](UI_MODULAR_PLAN.md) (ilk taslak) ve [`UI_MODULAR_PLAN_REVIEW.md`](UI_MODULAR_PLAN_REVIEW.md) (boşluk analizi) sonrasında, **Ponytail felsefesi** (YAGNI, sıfır şişkinlik, en kısa ve en sağlam yol) ile hazırlanmış nihai uygulama spesifikasyonudur.

---

## 1. Felsefe & Neden Ponytail?

İlk plan, henüz ortada olmayan projeler (WebAudio, CLI araçları) için Kervansaray içine 3000 satırlık dev bir HTML sekme sistemi kurmayı ve gerçek dışı metrikler ("0.8s", "yüzbinlerce kayıt") kullanmayı öneriyordu. `UI_MODULAR_PLAN_REVIEW.md` bu aşırı mühendislik (over-engineering) tuzaklarını net biçimde ortaya koydu.

**Ponytail Merdiveni Kararı:**
1. **Bu kodun var olmasına gerek var mı? (YAGNI):** HAYIR. Kervansaray içine sahte "Yakında" sekmeleri açmak gereksizdir. Portfolyo vitrini portfolyo reposunun (`yagizakkaya-site`) işidir.
2. **Kullanıcının gerçek derdi ne?:** Siteyi ilk kez ziyaret eden birinin (recruiter, mühendis, misafir) Kervansaray'ı 15 saniyede anlaması, aşırı teknik jargonla boğulmaması ve kırık/403 butonlarla karşılaşmaması.
3. **Çözüm:** Kervansaray'ın mevcut mimarisini bozmadan, sadece `index.html` üzerinde **3 cerrahi dokunuş** yapmak (~60 satır temiz HTML/CSS).

---

## 2. Çöpe Atılanlar (YAGNI / Yapılmayacaklar)

- ❌ **Kervansaray içine harici proje sekmeleri eklemek:** WebAudio ve CLI projeleri canlı birer web uygulaması olarak hazır olduğunda, portfolyonun kendi ana sayfası (`~/portfolio/public/urettiklerim.html`) üzerinden vitrine çıkarılacaktır. Kervansaray sadece Kervansaray kalır.
- ❌ **Tek dosyada çoklu proje durumu (state) ve SSE karmaşası:** Arka planda EventSource açıkken başka uygulamaların AudioContext'ini yönetmek gibi sızıntı kaynakları elendi.
- ❌ **Abartılı / Gerçek Dışı İfadeler:** `portfolio/AGENTS.md` kuralı: *"Sahte veri yok."* "0.8s" yerine dürüst metrikler yazılacaktır.

---

## 3. Uygulanacak 3 Cerrahi Dokunuş

### A. "Nedir & 3 Adımda Nasıl Denenir?" Hero Bloğu (~30 Satır)
Demodan hemen önce, teknik olmayan birinin bile tek bakışta anlayacağı sade bir karşılama kartı:

* **Değer Önerisi (Problem ➔ Çözüm):**
  > *"Giriş-çıkış yapan araçları kamera vizöründe otomatik tanıyan (ALPR) ve operatörün Türkçe sorularını SQL'e çevirerek anında raporlayan yapay zeka istihbarat motoru."*
* **Dürüst Metrik Rozetleri:**
  - `⚡ 0 ms (Önbellek) / ~5-15s (NVIDIA Nemotron 30B)`
  - `🛡️ SQL Kalkanı (Pre-flight Guardrail)`
  - `🔒 Salt-Okunur Public Demo`
  - `📊 220 Sentetik Test Olayı`
* **3 Adımda Hemen Deneyimleyin:**
  1. **1. Senaryo Seç:** Aşağıdaki 6 hazır güvenlik senaryosundan birine tıkla (Örn: *Kara Liste Alarmı* veya *Gece Girişi*).
  2. **2. Kamerayı İzle:** Vizörde yapay zekanın plakayı okuyup bariyer kararını anında vermesini gör.
  3. **3. Terminale Sor:** İster önerilen hazır soru çiplerine tıkla, ister Türkçe serbest sor; yapay zekanın veritabanından getirdiği gerçeği incele.

### B. Public Demoda 403 Veren Butonları Gizleme (ERROR.md / B1)
Public modda (`ENABLE_OPERATOR_ROUTES=false`):
* Tescil tablosundaki **"Düzenle"** ve **"Kaydet"** butonları gizlenir (Ziyaretçinin basıp 403 Forbidden alması ve projenin kırık sanılması engellenir).
* Varsa **"Demo Reset"** ve **"Kotayı Sıfırla"** gibi operatör aksiyonları gizlenir veya yerlerine `[🔒 Salt-Okunur Demo]` bilgi rozeti konur.
* Tablo, güvenilir ve temiz bir read-only güvenlik defteri olarak sunulur.

### C. Başlıkları İnsan Diline Çevirme (Çift Katmanlı Sadeleştirme)
Teknik derinlik rozetlerde ve İstihbarat Künyesinde korunurken, ana başlıklar herkesin anlayacağı Türkçe terimlere dönüştürülür:

| Mevcut Başlık | Ponytail Sadeleştirilmiş Başlık |
| :--- | :--- |
| `CANLI ALPR SİMÜLATÖRÜ` | **Canlı Kamera Akışı & Otomatik Plaka Okuma (ALPR)** |
| `DOĞAL DİL İSTİHBARAT TERMİNALİ` | **Doğal Dil İstihbarat Terminali** |
| `1. MODEL ANLATISI` | **1. Asistan Yanıtı (Özet)** |
| `2. SQL TOOL ÇAĞRISI` | **2. Çalıştırılan SQL Fonksiyonu** |
| `3. SONUÇ TABLOSU (VERİTABANI GERÇEĞİ)` | **3. Doğrulanmış Veritabanı Tablosu** |
| `ARAÇ TESCİL VE GÜVENLİK DEFTERİ` | **Araç Tescil ve Güvenlik Defteri** |
| `SON GÜVENLİK OLAYLARI AKIŞI` | **Son Güvenlik ve Geçiş Olayları Akışı** |

---

## 4. Kabul Kriterleri (Doğrulama)

> Uygulandı: commit `e8e0589` (yalnız `src/kervansaray/api/static/index.html`, +75/−19).

1. [x] **İlk İzlenim:** Hero bloğu değer önerisi + 3 adımlı rehber sunuyor.
2. [x] **Kırık Buton Yok:** Puppeteer ile public modda 21 buton tıklandı → 0 hata toast'ı, 0 pageerror. Operatör butonları (`[data-op]`) public DOM'dan siliniyor; operatör `?op=1` ile açar.
3. [x] **Dürüstlük:** Rozetler gerçek — `0 ms önbellek / ~5–15 sn canlı model`, `220 sentetik test olayı`. "0.8s" / "yüzbinlerce" ifadeleri kullanılmadı.
4. [x] **Sıfır Mimari Risk:** Caddy / API yolları / Docker'a dokunulmadı.

### Kapsam dışı bırakılanlar (UI_MODULAR_PLAN_REVIEW.md kuyruğu — sonraki tur)
- B2 Tailwind CDN → build'lenmiş CSS
- B3 a11y (tablist/aria/focus), B4 Open Graph meta
- B6 UI smoke testi (kalıcı)
- D2 onboarding funnel ölçümü
