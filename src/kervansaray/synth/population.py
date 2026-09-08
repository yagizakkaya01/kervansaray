"""Sabit populasyon ve gercekci giris/cikis ritmi (PROJECT_BRIEF S7/S8).

~200 arac: kayitli misafir, personel, tedarikci, bilinmeyen.
Ritim takvimi: check-in piki (13:00-20:00), checkout, vardiyalar, hafta sonu.
`persist()` populasyonu DB'ye yazar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Person, PersonKind, Registration, Vehicle

if TYPE_CHECKING:
    from .generator import SynthRandom

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

# Tam scripted ziyareti olan anomaliler - rhythm bunlari atlar.
_SCRIPTED = frozenset({"three_day_stay", "recurring_unregistered", "night_entry"})

_SHIFTS = {
    "morning": (time(7, 0), time(15, 0)),
    "evening": (time(15, 0), time(23, 0)),
    "night": (time(23, 0), time(7, 0)),  # ertesi gune tasar
}


# --- 1. Veri Yapilari -------------------------------------------------
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


@dataclass
class Visit:
    spec: VehicleSpec
    entry_ts: datetime
    exit_ts: datetime | None  # None = donem sonunda hala iceride


# --- 2. Populasyon Uretimi --------------------------------------------
def build_population(
    rng: SynthRandom, *, size: int, period_start: datetime, period_end: datetime
) -> Population:
    from .generator import random_plate, unique_plates

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

    for _ in range(n_guest):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="guest", person_name=name(),
                room_no=f"{r.randint(1, 6)}{r.randint(0, 9)}{r.randint(1, 9)}",
                registered=True, reg_from=period_start - timedelta(days=1),
                reg_to=period_end + timedelta(days=1),
            )
        )

    for _ in range(n_staff):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="staff", person_name=name(),
                registered=True, reg_from=period_start - timedelta(days=90), reg_to=None,
            )
        )

    for _ in range(n_vendor):
        pop.vehicles.append(
            VehicleSpec(
                plate=next(it), kind="vendor", person_name=r.choice(_VENDOR_CO),
                registered=True, reg_from=period_start - timedelta(days=30), reg_to=None,
            )
        )

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
    """Populasyonu DB'ye yazar ve VehicleSpec'lere DB id'lerini isler."""
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


# --- 3. Ritim ve Ziyaret Takvimi ---------------------------------------
def _at(day: datetime, t: time, jitter_min: int, r) -> datetime:
    base = day.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    return base + timedelta(minutes=r.randint(-jitter_min, jitter_min))


def _tri(r, lo: float, mode: float, hi: float) -> float:
    return r.triangular(lo, mode, hi)


def _time_of_day(day: datetime, hours: float, r) -> datetime:
    h = int(hours)
    m = int((hours - h) * 60)
    return day.replace(hour=min(h, 23), minute=m, second=r.randint(0, 59), microsecond=0)


def _days(start: datetime, end: datetime):
    d = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while d < end:
        yield d
        d += timedelta(days=1)


def build_visits(rng: SynthRandom, pop: Population) -> list[Visit]:
    visits: list[Visit] = []
    visits += _guest_visits(rng.for_stream("rhythm.guest"), pop)
    visits += _staff_visits(rng.for_stream("rhythm.staff"), pop)
    visits += _vendor_visits(rng.for_stream("rhythm.vendor"), pop)
    visits += _unknown_visits(rng.for_stream("rhythm.unknown"), pop)
    visits.sort(key=lambda v: v.entry_ts)
    return visits


def _guest_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    span_days = (pop.period_end - pop.period_start).days
    for spec in pop.by_kind("guest"):
        if spec.anomaly in _SCRIPTED:
            continue
        n_stays = r.choices((1, 2, 3, 4), weights=(45, 30, 18, 7))[0]
        used: list[tuple[datetime, datetime]] = []
        for _ in range(n_stays):
            for _try in range(6):
                offset = r.randint(0, max(0, span_days - 1))
                check_in_day = pop.period_start + timedelta(days=offset)
                if check_in_day.weekday() >= 4 and r.random() < 0.35:
                    pass
                nights = r.choices((1, 2, 3, 4, 5), weights=(30, 32, 20, 12, 6))[0]
                entry = _time_of_day(check_in_day, _tri(r, 13.0, 16.0, 20.0), r)
                exit_day = check_in_day + timedelta(days=nights)
                leave = _time_of_day(exit_day, _tri(r, 8.0, 10.5, 12.5), r)
                if any(entry < b and leave > a for a, b in used):
                    continue
                used.append((entry, leave))
                inside = leave <= pop.period_end
                out.append(Visit(spec, entry, leave if inside else None))
                break
    return out


def _staff_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    for spec in pop.by_kind("staff"):
        if spec.anomaly in _SCRIPTED:
            continue
        shift = r.choice(list(_SHIFTS))
        start_t, end_t = _SHIFTS[shift]
        for day in _days(pop.period_start, pop.period_end):
            weekend = day.weekday() >= 5
            if r.random() > (0.30 if weekend else 0.62):
                continue
            entry = _at(day, start_t, 25, r)
            end_day = day + timedelta(days=1) if shift == "night" else day
            leave = _at(end_day, end_t, 45, r)
            inside = leave <= pop.period_end
            out.append(Visit(spec, entry, leave if inside else None))
    return out


def _vendor_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    for spec in pop.by_kind("vendor"):
        if spec.anomaly in _SCRIPTED:
            continue
        for day in _days(pop.period_start, pop.period_end):
            if day.weekday() >= 5 or r.random() > 0.35:
                continue
            entry = _time_of_day(day, _tri(r, 8.0, 11.0, 15.0), r)
            leave = entry + timedelta(minutes=r.randint(20, 100))
            out.append(Visit(spec, entry, leave if leave <= pop.period_end else None))
    return out


def _unknown_visits(r, pop: Population) -> list[Visit]:
    out: list[Visit] = []
    span_days = max(1, (pop.period_end - pop.period_start).days)
    for spec in pop.by_kind("unknown"):
        if spec.anomaly in _SCRIPTED:
            continue
        for _ in range(r.choices((1, 2, 3), weights=(55, 33, 12))[0]):
            day = pop.period_start + timedelta(days=r.randrange(span_days))
            entry = _time_of_day(day, _tri(r, 7.0, 13.0, 21.0), r)
            leave = entry + timedelta(minutes=r.randint(15, 180))
            out.append(Visit(spec, entry, leave if leave <= pop.period_end else None))
    return out
