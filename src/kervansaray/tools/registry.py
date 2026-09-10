"""registry_summary — sisteme kayıtlı araç envanteri (v_events DEĞİL, `vehicles`).

Kapı hareketleri (`v_events`, ~38 tekil araç) ile tescil envanteri (`vehicles`)
ayrı gerçeklikler: kayıtlı araçların çoğu incelenen dönemde kapıdan hiç
geçmemiş olabilir. Bu tool zamandan bağımsız olarak `vehicles` + `persons` +
`registrations` tablolarını sayar.

"Kayıtlı araç" = sisteme bir kişiyle bağlı araç (`person_id IS NOT NULL`).
`aktif_tescil` = ayrıca geçerli bir `registrations` kaydı olanlar.

KARA LİSTE: `person_kind` enum'unda 'blacklist' yok — kara liste durumu
`vehicles.is_blacklisted` bayrağında. Bu yüzden tür dağılımında ve türe göre
filtrede kara listedeki araç kendi kovasında ('girisi_yasak') tutulur;
guest/staff/vendor sayımlarına DAHİL EDİLMEZ (yasaklı araç "misafir" sayılmaz).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from .types import ToolResult

_PERSON_KINDS = {"guest", "staff", "vendor"}
_UNKNOWN_ALIASES = {"unknown", "bilinmeyen", "kayitsiz", "kayıtsız", "sahipsiz"}
_BLACKLIST_ALIASES = {
    "blacklist", "kara liste", "kara_liste", "girisi yasak", "girişi yasak",
    "yasakli", "yasaklı", "hacizli",
}
# LLM'in "filtre yok" niyetiyle gönderebileceği değerler
_NO_FILTER = {"", "none", "null", "all", "hepsi", "tumu", "tümü", "toplam", "genel"}

# Kara listedeki aracı guest/staff/vendor sayımlarından dışlar
_NOT_BL = "COALESCE(v.is_blacklisted, FALSE) IS FALSE"


def registry_summary(db: DbSession, *, person_kind: str | None = None) -> ToolResult:
    """Tescil envanterinin anlık sayımı. Opsiyonel `person_kind` filtresi."""
    params: dict = {}
    pk = (person_kind or "").strip().lower()
    if pk in _NO_FILTER:
        pk = ""

    if pk in _BLACKLIST_ALIASES:
        pk = "blacklist"
        where = "v.is_blacklisted IS TRUE"
    elif pk in _UNKNOWN_ALIASES:
        pk = "unknown"
        where = f"v.person_id IS NULL AND {_NOT_BL}"
    elif pk:
        if pk not in _PERSON_KINDS:
            raise ValueError(
                f"person_kind {_PERSON_KINDS} / 'unknown' / 'blacklist' olmalı: {person_kind}"
            )
        where = f"v.person_id IS NOT NULL AND {_NOT_BL} AND p.kind::text = :pk"
        params["pk"] = pk
    else:
        where = "v.person_id IS NOT NULL"

    base = f"FROM vehicles v LEFT JOIN persons p ON p.id = v.person_id WHERE {where}"

    total = int(db.execute(text(f"SELECT count(*) {base}"), params).scalar_one())

    # Tür dağılımı: kara listedeki araç kendi kovasında, guest/staff/vendor'a karışmaz
    by_kind = [
        {"tur": r.k, "adet": int(r.n)}
        for r in db.execute(
            text(
                f"SELECT CASE WHEN v.is_blacklisted THEN 'girisi_yasak' "
                f"ELSE COALESCE(p.kind::text, 'kayitsiz') END AS k, count(*) AS n "
                f"{base} GROUP BY 1 ORDER BY n DESC"
            ),
            params,
        )
    ]

    blacklisted = int(
        db.execute(text(f"SELECT count(*) {base} AND v.is_blacklisted"), params).scalar_one()
    )
    active_reg = int(
        db.execute(
            text(
                f"SELECT count(*) {base} AND EXISTS ("
                "SELECT 1 FROM registrations r WHERE r.vehicle_id = v.id "
                "AND (r.valid_to IS NULL OR r.valid_to >= now()))"
            ),
            params,
        ).scalar_one()
    )
    seen = int(
        db.execute(
            text(
                f"SELECT count(*) {base} AND EXISTS ("
                "SELECT 1 FROM events e WHERE e.vehicle_id = v.id)"
            ),
            params,
        ).scalar_one()
    )

    return ToolResult(
        tool="registry_summary",
        params={"person_kind": pk} if pk else {},
        scalar={
            "kayitli_arac": total,
            "aktif_tescil": active_reg,
            "kara_liste": blacklisted,
            "kapidan_gecmis": seen,
        },
        rows=by_kind,
    )
