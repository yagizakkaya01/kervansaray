"""Sentetik operasyonel notlar ve prosedürler (PROJECT_BRIEF S3.6, ROADMAP Faz 6).

Vardiya devir notları, güvenlik raporları, teknik arıza kayıtları ve VIP prosedürleri.
Deterministik 15 operasyonel kayıt (Ponytail: sıfır yapay jeneratör karmaşıklığı).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))

OPERATIONAL_NOTES: list[dict[str, str | datetime]] = [
    {
        "ts": datetime(2026, 4, 2, 8, 30, tzinfo=TR),
        "author": "Yönetim",
        "body": (
            "Prosedür: VIP misafir araçları ana giriş karşısındaki Doğu Otoparkı A bloğuna "
            "yönlendirilir. Resepsiyon vale hizmeti sağlar."
        ),
    },
    {
        "ts": datetime(2026, 4, 5, 6, 15, tzinfo=TR),
        "author": "Lojistik Şefi",
        "body": (
            "Prosedür: Mutfak ve teknik malzeme tedarikçi araçları yalnızca sabah 06:00 - 09:00 "
            "saatleri arasında arka servis kapısını kullanabilir."
        ),
    },
    {
        "ts": datetime(2026, 4, 10, 14, 20, tzinfo=TR),
        "author": "Teknik Servis",
        "body": (
            "Giriş bariyer kolu B motorunda temassızlık tespit edildi, parça siparişi verildi. "
            "Geçişler manuel kontrollü sağlanıyor."
        ),
    },
    {
        "ts": datetime(2026, 4, 12, 11, 0, tzinfo=TR),
        "author": "Teknik Servis",
        "body": (
            "Giriş bariyer kolu B arızası giderildi. Sensör kalibrasyonu ve motor dişlisi "
            "yenilendi, normal çalışma düzenine dönüldü."
        ),
    },
    {
        "ts": datetime(2026, 4, 15, 3, 25, tzinfo=TR),
        "author": "Gece Güvenlik",
        "body": (
            "Gece devriyesi: 38HE907 plakalı araç saat 03:15 civarında nizamiye önünde "
            "10 dakika durakladı. Sürücü misafir olduğunu belirtti, teyit alındıktan "
            "sonra geçiş verildi."
        ),
    },
    {
        "ts": datetime(2026, 4, 18, 9, 45, tzinfo=TR),
        "author": "Güvenlik Amiri",
        "body": (
            "Güvenlik talimatı: Kara listede bulunan plakalar (özellikle 06ANK06 ve 34VIP99) "
            "sisteme düştüğünde araç durdurulacak ve derhal nöbetçi amire haber verilecektir."
        ),
    },
    {
        "ts": datetime(2026, 4, 22, 23, 10, tzinfo=TR),
        "author": "Vardiya Amiri",
        "body": (
            "Vardiya devir: Doğu otoparkı aydınlatma lambası L-4 arızalı, yarın sabah teknik "
            "ekibe iletilmeli. Saha doluluğu sakin."
        ),
    },
    {
        "ts": datetime(2026, 4, 25, 17, 30, tzinfo=TR),
        "author": "Teknik Servis",
        "body": (
            "2 numaralı plaka tanıma kamerası lensi temizlendi ve odak ayarı yapıldı. "
            "Gece görüş IR aydınlatması test edildi."
        ),
    },
    {
        "ts": datetime(2026, 5, 1, 4, 10, tzinfo=TR),
        "author": "Gece Güvenlik",
        "body": (
            "Gece devriyesi: Saat 03:45'te otopark alt katında plakasız motosiklet görüldü, "
            "devriye görevlisi kontrol etti, personel motoru olduğu anlaşıldı."
        ),
    },
    {
        "ts": datetime(2026, 5, 4, 8, 0, tzinfo=TR),
        "author": "Güvenlik Amiri",
        "body": (
            "Prosedür: 48 saatten uzun süre sahada kalan araçlar (overstay) tespit edildiğinde "
            "resepsiyon aranarak oda sahibiyle irtibata geçilecek."
        ),
    },
    {
        "ts": datetime(2026, 5, 7, 2, 40, tzinfo=TR),
        "author": "Gece Güvenlik",
        "body": (
            "Gece 02:30'da gelen 15VF6810 plakalı araç misafir otoparkına yönlendirildi. "
            "Giriş kaydı yapıldı."
        ),
    },
    {
        "ts": datetime(2026, 5, 12, 16, 0, tzinfo=TR),
        "author": "Yönetim",
        "body": (
            "Duyuru: 15 Mayıs Cuma günü otopark zemin çizgileri boyanacaktır. B ve C blokları "
            "dönüşümlü olarak araç girişine kapatılacaktır."
        ),
    },
    {
        "ts": datetime(2026, 5, 16, 10, 30, tzinfo=TR),
        "author": "Vardiya Amiri",
        "body": (
            "Boyama çalışması tamamlandı. Tüm otopark blokları ve yönlendirme tabelaları "
            "normal kullanıma açıldı."
        ),
    },
    {
        "ts": datetime(2026, 5, 20, 19, 15, tzinfo=TR),
        "author": "Resepsiyon",
        "body": (
            "VIP misafir Sayın Kaya için Doğu Otoparkı 01 no'lu yer ayrıldı. "
            "Araç plakası: 34KAY44."
        ),
    },
    {
        "ts": datetime(2026, 5, 25, 22, 50, tzinfo=TR),
        "author": "Gece Güvenlik",
        "body": (
            "Vardiya devir: Genel asayiş berkemal. Tüm kameralar devrede, nizamiye bariyerleri "
            "sorunsuz çalışıyor."
        ),
    },
]


def get_synthetic_notes() -> list[dict[str, str | datetime]]:
    """Tüm sentetik operasyonel ve prosedür notlarını döner."""
    return list(OPERATIONAL_NOTES)
