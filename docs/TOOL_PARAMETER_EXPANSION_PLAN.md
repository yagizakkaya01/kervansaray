# Tool Parametre Genişletme Planı (Ponytail Yaklaşımı)

> **Özet:** 6 tool sayısı dondurulur; yeni tool YAZILMAZ.
> Kör noktalar (kişi adı, unvan/rol, personel/misafir ayrımı, tekil plaka sayımı)
> mevcut `query_events` ve `aggregate_events` tool'larına eklenecek **4 yalın parametre**
> ve veritabanına **1 opsiyonel kolon (`title`)** ile çözülür.
> 
> Referans: `docs/TOOL_CONSISTENCY_PLAN.md`, `src/kervansaray/tools/schemas.py`.
> Tarih: 2026-09-10. Karar Yöntemi: `/grill-me` + `/ponytail`.

---

## 1. Neden Yeni Tool Değil, Parametre Genişletme?

1. **LLM Kararsızlığını Önleme:** Küçük modeller (Nemotron, Gemini Flash) 5–7 tool arasında en yüksek başarıyı gösterir. 7. veya 8. bir tool eklemek (`search_person_events` vb.) modelin tool seçim kaprisini katlar.
2. **Ortogonalite:** Mevcut 6 tool zaten 6 temel soru tipini kapsar (Liste, Sayım, Tek Plaka, Doluluk, Anomali, Not).
3. **Merdiven Kuralı (Ponytail):** `v_events` zaten `persons` tablosuna bağlı. Eksik olan yeni bir SQL sorgusu değil, mevcut sorgudaki iki adet `WHERE` filtresidir.

---

## 2. Parametre Matrisi

| Tool | Mevcut Parametreler | Eklenecek Parametreler | Çözülen Yeni Senaryolar |
|---|---|---|---|
| **`query_events`** | `start`, `end`, `plate`, `direction`, `registered`, `limit` | **`person`** `(str)`<br>*(Ad veya unvan araması)*<br><br>**`person_kind`** `(str)`<br>*(guest / staff / vendor)* | • *"Güvenlik müdürü ne zaman girdi?"* (`person="güvenlik müdürü"`)<br>• *"Ahmet Yılmaz bugün geldi mi?"* (`person="Ahmet Yılmaz"` )<br>• *"Dün gelen tedarikçi araçlarını listele"* (`person_kind="vendor"`)<br>• *"Giriş yapan misafir araçları"* (`person_kind="guest"`) |
| **`aggregate_events`** | `metric`, `start`, `end`, `group_by`, `direction`, `registered` | **`plate`** `(str)`<br>*(Belirli plaka filtresi)*<br><br>**`person_kind`** `(str)`<br>*(guest / staff / vendor)* | • *"26 ABC 2626 bu ay toplam kaç kez geldi?"* (`plate="26ABC2626"`)<br>• *"Nisan ayında kaç personel aracı giriş yaptı?"* (`person_kind="staff"`)<br>• *"Geçen hafta tesise kaç tekil tedarikçi aracı girdi?"* (`metric="unique_plates"`, `person_kind="vendor"`) |
| **`vehicle_history`** | `plate` | *(Değişiklik yok - Donduruldu)* | Sırf tekil plaka derinliği (seanslar, kalış süreleri, tescil kartı). Plaka bilinmiyorsa `query_events(person=...)` kullanılır. |
| **`occupancy`** | `as_of` | *(Değişiklik yok - Donduruldu)* | Anlık/tarihli otopark doluluğu (0 ms / 20s TTL). |
| **`find_anomalies`** | `rule`, `start`, `end`, `min_visits`, `overstay_hours` | *(Değişiklik yok - Donduruldu)* | 4 kural (night_entry, overstay, blacklist, unregistered_recurring) kural bazlı kalır. |
| **`search_notes`** | `query`, `author`, `limit` | *(Değişiklik yok - Donduruldu)* | Vardiya devir notları, arıza kayıtları ve VIP prosedür metinleri. |

---

## 3. Katman Katman Yapılacak Değişiklikler

### A. Veritabanı & View Katmanı
1. **Alembic Migration (`0003_add_title_to_persons.py`):**
   - `persons` tablosuna `title = Column(String(100), nullable=True)` eklenir (örn: "Güvenlik Amiri", "Lojistik Şefi", "Genel Müdür").
2. **`v_events` View Güncellemesi (`src/kervansaray/db/views.py`):**
   - `SELECT ... p.title AS person_title ...` alanı view'a dahil edilir.
3. **Sentetik Nüfus (`src/kervansaray/synth/population.py`):**
   - Personel (`staff`) üretilirken gerçekçi unvanlar atanır (Güvenlik Amiri, Teknik Sorumlu, Resepsiyonist vb.).

### B. Tool Mantığı & SQL (`src/kervansaray/tools/`)
1. **`events.py :: query_events`:**
   ```python
   if person:
       where.append("(person_name ILIKE :person OR person_title ILIKE :person)")
       params["person"] = f"%{person}%"
   if person_kind:
       _check(person_kind in _PERSON_KINDS, f"gecersiz person_kind: {person_kind}")
       where.append("person_kind = :person_kind")
       params["person_kind"] = person_kind
   ```
2. **`events.py :: aggregate_events`:**
   ```python
   if plate:
       where.append("plate = :plate")
       params["plate"] = canonicalize(plate)
   if person_kind:
       _check(person_kind in _PERSON_KINDS, f"gecersiz person_kind: {person_kind}")
       where.append("person_kind = :person_kind")
       params["person_kind"] = person_kind
   ```
3. **`schemas.py`:**
   - `FUNCTION_DECLARATIONS` içinde `query_events` ve `aggregate_events` şemalarına bu parametreler tipli ve Türkçe açıklamalarıyla eklenir.

### C. Sistem Talimatı & Few-Shot (`src/kervansaray/llm/prompts.py`)
- `FEW_SHOT_EXAMPLES` listesine 2 yeni hedefli örnek eklenir:
  - `"Güvenlik müdürü ne zaman çıktı?"` → `query_events(person="güvenlik müdürü", direction="exit")`
  - `"Bu ay kaç personel aracı geldi?"` → `aggregate_events(person_kind="staff", metric="count", direction="entry")`

---

## 4. Efor, Risk ve Kod Büyüklüğü

| Metrik | Değer | Not |
|---|---|---|
| **Yeni Dosya Sayısı** | 1 (`alembic/versions/0003_add_title_to_persons.py`) | ~20 satır |
| **Mevcut Dosya Değişiklikleri** | 4 dosya (`models.py`, `views.py`, `events.py`, `schemas.py`) | Toplam ~35 satır diff |
| **Yeni Bağımlılık** | **0** | Tamamen stdlib + SQLAlchemy |
| **Tahmini Efor** | **~45 dakika** | Testler dahil |
| **Regresyon Riski** | **Çok Düşük** | Tüm parametreler opsiyonel (`default=None`), mevcut testleri kırmaz. |
