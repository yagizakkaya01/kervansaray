"""Sabit populasyon: personler, araclar, kayitlar (PROJECT_BRIEF S7/S8).

~200 arac: kayitli misafir, personel, tedarikci, bilinmeyen. Deterministik
(tek `Random(seed)`). `persist()` bunlari DB'ye yazar - bu referans veridir,
olay degil, o yuzden ingest API'sinden gecmez.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Person, PersonKind, Registration, Vehicle

from .plates import random_plate, unique_plates
from .rng import SynthRandom

# Populasyon dagilimi (varsayilan ~200 arac).
GUEST_SHARE = 0.55
STAFF_SHARE = 0.20
VENDOR_SHARE = 0.10
# kalan -> bilinmeyen (kayitsiz)

# Kesin-sentetik araclar: il kodu 82-99 (Turkiye'de yok). S8 konvansiyonu -
# gecersiz-il ret yolunu test etmek icin birkac tane uretilir.
N_SYNTHETIC = 3

_FIRST = [
    "Ahmet", "Mehmet", "Ayse", "Fatma", "Mustafa", "Emine", "Ali", "Hatice",
    "Huseyin", "Zeynep", "Hasan", "Elif", "Ibrahim", "Meryem", "Omer", "Sena",
    "Yusuf", "Derya", "Murat", "Buse", "Kerem", "Irem", "Baris", "Ceren",
]
_LAST = [
    "Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Yildiz", "Yildirim", "Ozturk",
    "Aydin", "Ozdemir", "Arslan", "Dogan", "Kilic", "Aslan", "Cetin", "Kara",
]
_VENDOR_CO = [
    "Marmara Lojistik", "Ege Gida", "Anadolu Tedarik", "Bosphorus Catering",
    "Yildiz Temizlik", "Deniz Nakliyat", "Kervan Ticaret",
]


@dataclass
class VehicleSpec:
    """Bir aracin uretim-zamani ground-truth'u (DB id'leri persist sonrasi dolar)."""

    plate: str
    kind: str  # "guest" | "staff" | "vendor" | "unknown"
    person_name: str | None = None
    room_no: str | None = None
    is_blacklisted: bool = False
    registered: bool = False
    synthetic: bool = False  # il kodu 82-99, kesin test verisi (S8)
    known: bool = True  # False -> DB'ye yazilmaz (sistemin tanimadigi arac)
    anomaly: str | None = None  # dolu ise rhythm bu araci atlar; sadece scripted ziyaret
    reg_from: datetime | None = None
    reg_to: datetime | None = None
    vehicle_id: int | None = None
    person_id: int | None = None


@dataclass
class Population:
    period_start: datetime
    period_end: datetime
    vehicles: list[VehicleSpec] = field(default_factory=list)

    def by_kind(self, kind: str) -> list[VehicleSpec]:
        return [v for v in self.vehicles if v.kind == kind]

    def find(self, plate: str) -> VehicleSpec | None:
        return next((v for v in self.vehicles if v.plate == plate), None)


def build_population(
    rng: SynthRandom, *, size: int, period_start: datetime, period_end: datetime
) -> Population:
    r = rng.for_stream("population")
    n_guest = round(size * GUEST_SHARE)
    n_staff = round(size * STAFF_SHARE)
    n_vendor = round(size * VENDOR_SHARE)
    n_unknown = size - n_guest - n_staff - n_vendor

    plates = unique_plates(r, size)
    r.shuffle(plates)
    it = iter(plates)

    pop = Population(period_start=period_start, period_end=period_end)

    def name() -> str:
        return f"{r.choice(_FIRST)} {r.choice(_LAST)}"

    # Misafirler: kayitli, oda numarali. Kayit periyodun tamamini kapsar
    # (misafir donem boyunca birden fazla konaklama yapabilir - rhythm bunu uretir).
    for _ in range(n_guest):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="guest", person_name=name(),
                room_no=f"{r.randint(1, 6)}{r.randint(0, 9)}{r.randint(1, 9)}",
                registered=True, reg_from=period_start - timedelta(days=1),
                reg_to=period_end + timedelta(days=1),
            )
        )

    # Personel: uzun sureli kayit, oda yok.
    for _ in range(n_staff):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="staff", person_name=name(),
                registered=True, reg_from=period_start - timedelta(days=90), reg_to=None,
            )
        )

    # Tedarikciler: sirket adi, kayitli.
    for _ in range(n_vendor):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="vendor", person_name=r.choice(_VENDOR_CO),
                registered=True, reg_from=period_start - timedelta(days=30), reg_to=None,
            )
        )

    # Bilinmeyenler: kisi yok, kayit yok.
    for _ in range(n_unknown):
        pop.vehicles.append(VehicleSpec(plate=next(it), kind="unknown"))

    # Kesin-sentetik (il kodu 82-99). Plaka havuzu disindan uretilir.
    existing = {v.plate for v in pop.vehicles}
    for _ in range(N_SYNTHETIC):
        while (p := random_plate(r, synthetic=True)) in existing:
            pass
        existing.add(p)
        pop.vehicles.append(VehicleSpec(plate=p, kind="unknown", synthetic=True))

    return pop


def persist(db: DbSession, pop: Population) -> None:
    """Populasyonu DB'ye yazar ve VehicleSpec'lere DB id'lerini isler.

    Bos bir sema bekler (ROADMAP Faz 2: `synth --reset` ile TRUNCATE edilir).

    Kesin-sentetik araclar (il kodu 82-99) DB'ye YAZILMAZ - onlar "bilinmeyen,
    imkansiz plakali" araci temsil eder; olaylari mutabakatta unmatched kalir
    ve ileride gecersiz-il ret yolunun test fikstürü olur (S8).
    """
    for spec in pop.vehicles:
        if spec.synthetic or not spec.known:
            continue
        person = None
        if spec.person_name is not None:
            kind = (
                PersonKind(spec.kind)
                if spec.kind in PersonKind.__members__
                else PersonKind.guest
            )
            person = Person(name=spec.person_name, kind=kind, room_no=spec.room_no)
            db.add(person)
            db.flush()
            spec.person_id = person.id

        vehicle = Vehicle(
            plate=spec.plate,
            person_id=person.id if person else None,
            label=_label(spec),
            is_blacklisted=spec.is_blacklisted,
        )
        db.add(vehicle)
        db.flush()
        spec.vehicle_id = vehicle.id

        if spec.registered and person is not None:
            db.add(
                Registration(
                    vehicle_id=vehicle.id, person_id=person.id,
                    valid_from=spec.reg_from, valid_to=spec.reg_to,
                )
            )
    db.flush()


def _label(spec: VehicleSpec) -> str | None:
    if spec.kind == "guest":
        return f"Misafir - Oda {spec.room_no}"
    if spec.kind == "staff":
        return "Personel"
    if spec.kind == "vendor":
        return f"Tedarikci - {spec.person_name}"
    return None


def is_empty(db: DbSession) -> bool:
    return db.scalar(select(Vehicle.id).limit(1)) is None
