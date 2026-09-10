"""registry_summary — tescil envanteri sayımı (kapı hareketlerinden bağımsız).

Referans: docs/REGISTRY_INVENTORY_QUERY_REVIEW.md (Option A).
"""
from datetime import timedelta

import pytest

from kervansaray.db.models import PersonKind, Registration
from kervansaray.tools import dispatch_tool, registry_summary
from tests._helpers import BASE_TS, seed_vehicle


def _inventory(db):
    # 3 personel, 2 misafir, 1 tedarikçi, 2 sahipsiz (person_id NULL)
    for i in range(3):
        seed_vehicle(db, f"06AAA{i}", person_name=f"Personel {i}", kind=PersonKind.staff)
    for i in range(2):
        seed_vehicle(db, f"34BBB{i}", person_name=f"Misafir {i}", kind=PersonKind.guest)
    seed_vehicle(db, "35CCC0", person_name="Tedarik A.Ş.", kind=PersonKind.vendor)
    seed_vehicle(db, "80DDD0")  # sahipsiz
    seed_vehicle(db, "80DDD1")  # sahipsiz
    # 1 kara liste — person.kind hâlâ 'guest' (canlı 34VIP99 senaryosu gibi):
    # blacklist bir PersonKind değil, Vehicle.is_blacklisted bayrağı.
    seed_vehicle(db, "34XYZ99", person_name="Yasaklı", kind=PersonKind.guest, blacklisted=True)
    db.commit()


def test_total_and_bucket_split(db):
    _inventory(db)
    r = registry_summary(db)
    # 3 staff + 2 guest + 1 vendor + 1 kara-liste(guest) = 7 kişiye bağlı; 2 sahipsiz hariç
    assert r.scalar["kayitli_arac"] == 7
    assert r.scalar["kara_liste"] == 1
    kinds = {row["tur"]: row["adet"] for row in r.rows}
    assert kinds["staff"] == 3
    assert kinds["guest"] == 2          # kara listedeki 'guest' kişi buraya SAYILMAZ
    assert kinds["vendor"] == 1
    assert kinds["girisi_yasak"] == 1   # kendi kovasında


def test_person_kind_guest_excludes_blacklisted(db):
    _inventory(db)
    # 3 guest-kind araç var ama biri kara listede -> misafir sayımına girmez
    assert registry_summary(db, person_kind="guest").scalar["kayitli_arac"] == 2


def test_person_kind_blacklist_bucket_and_aliases(db):
    _inventory(db)
    assert registry_summary(db, person_kind="blacklist").scalar["kayitli_arac"] == 1
    assert registry_summary(db, person_kind="kara liste").scalar["kayitli_arac"] == 1
    assert registry_summary(db, person_kind="girişi yasak").scalar["kayitli_arac"] == 1


def test_person_kind_staff_filter(db):
    _inventory(db)
    assert registry_summary(db, person_kind="staff").scalar["kayitli_arac"] == 3


def test_unknown_counts_ownerless(db):
    _inventory(db)
    assert registry_summary(db, person_kind="unknown").scalar["kayitli_arac"] == 2


def test_active_registration_subcount(db):
    v = seed_vehicle(db, "06AK0052", person_name="Aktif Tescil", kind=PersonKind.guest)
    db.add(Registration(
        vehicle_id=v.id, person_id=v.person_id,
        valid_from=BASE_TS - timedelta(days=10), valid_to=None,
    ))
    seed_vehicle(db, "06AK0053", person_name="Tescilsiz", kind=PersonKind.guest)
    db.commit()
    r = registry_summary(db)
    assert r.scalar["kayitli_arac"] == 2
    assert r.scalar["aktif_tescil"] == 1


def test_invalid_person_kind_raises(db):
    with pytest.raises(ValueError):
        registry_summary(db, person_kind="patron")


@pytest.mark.parametrize("junk", ["None", "null", "", "  ", "hepsi", "toplam"])
def test_no_filter_aliases_treated_as_unfiltered(db, junk):
    _inventory(db)
    assert registry_summary(db, person_kind=junk).scalar["kayitli_arac"] == 7


def test_dispatch_wiring(db):
    _inventory(db)
    res = dispatch_tool(db, "registry_summary", {"person_kind": "staff"})
    assert res.note is None
    assert res.scalar["kayitli_arac"] == 3
