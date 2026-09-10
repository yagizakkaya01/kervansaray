"""LLM function calling icin standart tool semalari (PROJECT_BRIEF S3.2).

Groq, OpenAI ve Google Gemini formatlarini destekler.
Tum parametreler tipli, aciklama metinleri Turkce ve enum degerleri net tanimlidir.
"""
from __future__ import annotations

from typing import Any

# Ortak JSON Schema fonksiyon bildirimleri
FUNCTION_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "query_events",
        "description": (
            "Belirli bir zaman aralığındaki araç geçiş olaylarını listeler. "
            "Plaka, yön (entry/exit) ve kayıt durumuna göre filtrelenebilir. "
            "En fazla 50 satır döner. "
            "Toplam sayı veya istatistik için aggregate_events kullanılmalıdır."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": (
                        "Aralık başlangıcı ISO 8601 zaman damgası "
                        "(örn: '2026-04-15T00:00:00+03:00')."
                    ),
                },
                "end": {
                    "type": "string",
                    "description": (
                        "Aralık bitişi ISO 8601 zaman damgası "
                        "(örn: '2026-04-16T00:00:00+03:00')."
                    ),
                },
                "plate": {
                    "type": "string",
                    "description": "Filtrelenecek plaka (örn: '34ABC123').",
                },
                "person": {
                    "type": "string",
                    "description": (
                        "Kişi ADI veya UNVANI ile filtre (örn: 'Ahmet Yılmaz', "
                        "'güvenlik müdürü', 'genel müdür'). Ad, unvan ve araç etiketinde "
                        "aksan-duyarsız aranır. SADECE kullanıcı bir kişi adı ya da "
                        "unvan belirttiyse doldur; aksi halde BOŞ bırak."
                    ),
                },
                "person_kind": {
                    "type": "string",
                    "enum": ["guest", "staff", "vendor", "unknown"],
                    "description": (
                        "Kişi türü filtresi: 'guest' (misafir), 'staff' (personel), "
                        "'vendor' (tedarikçi), 'unknown' (eşleşmeyen/kayıtsız araç). "
                        "SADECE kullanıcı tür belirttiyse ('personel araçları', "
                        "'tedarikçiler') doldur."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["entry", "exit"],
                    "description": "Geçiş yönü: 'entry' (giriş) veya 'exit' (çıkış).",
                },
                "registered": {
                    "type": "boolean",
                    "description": (
                        "True: yalnızca kayıtlı araçlar (misafir/personel/tedarikçi). "
                        "False: kayıtsız/bilinmeyen araçlar."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimum satır sayısı (1-50 arası, varsayılan 50).",
                },
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "aggregate_events",
        "description": (
            "Belirli bir zaman aralığındaki araç hareketlerinin toplam sayısını "
            "veya kırılımlı (gruplanmış) istatistiklerini hesaplar. "
            "Kaç araç girdi, dağılım gibi sayım sorularında bu tool çağrılmalıdır."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": (
                        "Aralık başlangıcı ISO 8601 formatında "
                        "(örn: '2026-04-01T00:00:00+03:00')."
                    ),
                },
                "end": {
                    "type": "string",
                    "description": (
                        "Aralık bitişi ISO 8601 formatında "
                        "(örn: '2026-05-01T00:00:00+03:00')."
                    ),
                },
                "group_by": {
                    "type": "string",
                    "enum": ["day", "hour", "direction", "match_status", "person_kind"],
                    "description": (
                        "Gruplama boyutu: 'day' (günlük), 'hour' (saatlik), "
                        "'direction' (giriş/çıkış), 'match_status' (eşleşme durumu), "
                        "'person_kind' (kişi türü: guest/staff/vendor/unknown). "
                        "Boş bırakılırsa tek toplam döner."
                    ),
                },
                "metric": {
                    "type": "string",
                    "enum": ["count", "unique_plates"],
                    "description": (
                        "'count': toplam geçiş adedi, 'unique_plates': tekil araç sayısı."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["entry", "exit"],
                    "description": "Geçiş yönü filtresi: 'entry' (giriş) veya 'exit' (çıkış).",
                },
                "registered": {
                    "type": "boolean",
                    "description": (
                        "True: yalnızca kayıtlı araçlar. False: kayıtsız/bilinmeyen araçlar."
                    ),
                },
                "plate": {
                    "type": "string",
                    "description": (
                        "Tek bir plakayla sınırla (örn: '26ABC2626'). Bir aracın "
                        "belirli dönemdeki toplam geçiş sayısı için kullan."
                    ),
                },
                "person_kind": {
                    "type": "string",
                    "enum": ["guest", "staff", "vendor", "unknown"],
                    "description": (
                        "Kişi türüne göre say ('kaç personel aracı girdi'). SADECE "
                        "kullanıcı tür belirttiyse doldur."
                    ),
                },
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "vehicle_history",
        "description": (
            "Tek bir aracın tüm geçmişini, tescil bilgilerini, giriş/çıkış hareketlerini "
            "ve otopark seanslarını (kalış süreleri, şu an içeride mi) detaylı getirir. "
            "Araç PLAKAYLA ya da SAHİBİNİN ADI/UNVANIYLA ('Tarık Akkaya', 'güvenlik "
            "müdürü') sorgulanabilir — 'X'in aracı hangisi', 'X'in plakası ne', 'X ne "
            "zaman geldi' soruları buraya gelir. En az biri (plate veya person) verilmeli."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Sorgulanacak plaka (örn: '34ABC123').",
                },
                "person": {
                    "type": "string",
                    "description": (
                        "Araç sahibinin adı veya unvanı (örn: 'Tarık Akkaya', "
                        "'güvenlik müdürü'). Plaka bilinmiyorsa bunu kullan; "
                        "aksan-duyarsız aranır."
                    ),
                },
            },
        },
    },
    {
        "name": "find_anomalies",
        "description": (
            "Belirli bir zaman penceresinde kural tabanlı otopark anomalilerini tarar ve bulur. "
            "Kurallar: 'unregistered_recurring' (çok kez gelen kayıtsız araç), "
            "'overstay' (uzun süre çıkış yapmayan araç), 'blacklist' (kara listedeki araç), "
            "'night_entry' (gece 00:00-05:00 arası olağandışı girişler)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rule": {
                    "type": "string",
                    "enum": ["unregistered_recurring", "overstay", "blacklist", "night_entry"],
                    "description": "Taranacak anomali kuralı türü.",
                },
                "start": {
                    "type": "string",
                    "description": (
                        "Pencere başlangıcı ISO 8601 (örn: '2026-04-01T00:00:00+03:00')."
                    ),
                },
                "end": {
                    "type": "string",
                    "description": (
                        "Pencere bitişi ISO 8601 (örn: '2026-05-01T00:00:00+03:00')."
                    ),
                },
                "min_visits": {
                    "type": "integer",
                    "description": (
                        "'unregistered_recurring' için min giriş eşiği (varsayılan 3)."
                    ),
                },
                "overstay_hours": {
                    "type": "integer",
                    "description": (
                        "'overstay' kuralı için min kalış süresi saati (varsayılan 48 saat)."
                    ),
                },
            },
            "required": ["rule", "start", "end"],
        },
    },
    {
        "name": "occupancy",
        "description": (
            "Otopark sahasında belirli bir anda (veya şu an) kaç aracın içeride olduğunu "
            "ve bu araçların plaka listesini döner. Eksik çıkış kirini hesaba katar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "as_of": {
                    "type": "string",
                    "description": (
                        "Doluluk sorgulanan an (ISO 8601, örn: '2026-04-15T14:30:00+03:00'). "
                        "Boş ise şu anki zaman."
                    ),
                },
            },
        },
    },
    {
        "name": "search_notes",
        "description": (
            "Vardiya notları, güvenlik raporları, teknik arızalar, VIP protokolleri "
            "ve operasyonel PROSEDÜR metinlerinde serbest metin araması yapar. "
            "DİKKAT: Sayı / adet / istatistik / envanter / 'kaç araç' sorularında "
            "ASLA bu aracı çağırma — notlar yalnızca prosedür ve vardiya devir "
            "metinleridir, veri içermez."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Aranacak anahtar kelime veya serbest metin "
                        "(örn: 'bariyer', 'VIP', 'arıza', '38HE907')."
                    ),
                },
                "author": {
                    "type": "string",
                    "description": (
                        "İsteğe bağlı: notu yazan birim. YALNIZCA kullanıcı açıkça "
                        "bir birim adı yazdıysa doldur ('Hukuk Birimi'nin notu', "
                        "'nöbetçi amirin yazdığı'). Genel prosedür/konu aramasında "
                        "BOŞ BIRAK."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimum sonuç sayısı (1-50 arası, varsayılan 10).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "registry_summary",
        "description": (
            "Sisteme KAYITLI araç envanterinin anlık sayımını verir (kapıdan geçen "
            "araçlar değil, tescil defterindeki tüm araçlar). "
            "'Sistemde kaç araç kayıtlı', 'tescilli araç envanteri', 'kaç kayıtlı "
            "personel/misafir/tedarikçi aracı var' gibi ENVANTER sorularında bu "
            "aracı çağır. Zamandan bağımsızdır; tarih parametresi almaz."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "person_kind": {
                    "type": "string",
                    "enum": ["guest", "staff", "vendor", "blacklist"],
                    "description": (
                        "İsteğe bağlı tür filtresi: 'guest' (misafir), 'staff' "
                        "(personel), 'vendor' (tedarikçi), 'blacklist' (kara liste / "
                        "girişi yasak). "
                        "YALNIZCA kullanıcı cümlesinde bu türlerden BİRİ açıkça "
                        "geçiyorsa doldur ('kaç PERSONEL aracı', 'kaç KARA LİSTE'). "
                        "Genel 'toplam kaç araç kayıtlı / envanter sayısı' "
                        "sorusunda BU PARAMETREYİ GÖNDERME; araç zaten tüm türleri "
                        "sayıp dağılımı verir (kara liste ayrı kovada)."
                    ),
                },
            },
        },
    },
]

# Gemini formatı: {"function_declarations": [...]}
GEMINI_FUNCTION_DECLARATIONS = FUNCTION_DECLARATIONS

# OpenAI / Groq formatı: [{"type": "function", "function": {...}}, ...]
OPENAI_TOOLS = [{"type": "function", "function": f} for f in FUNCTION_DECLARATIONS]
