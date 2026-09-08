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
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "vehicle_history",
        "description": (
            "Tek bir plakanın tüm geçmişini, kayıt bilgilerini, giriş/çıkış hareketlerini "
            "ve otopark seanslarını (kalış süreleri, şu an içeride mi) detaylı olarak getirir."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Sorgulanacak plaka (örn: '34ABC123').",
                },
            },
            "required": ["plate"],
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
]

# Gemini formatı: {"function_declarations": [...]}
GEMINI_FUNCTION_DECLARATIONS = FUNCTION_DECLARATIONS
