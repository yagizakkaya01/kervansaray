"""Enjekte edilen anomaliler (PROJECT_BRIEF S8).

  - uc gun kalan arac
  - bes gece ust uste gelen kayitsiz arac
  - 03:00 girisi
  - kara listedeki plaka

Her anomali icin ozel bir arac (anomaly!=None -> rhythm atlar) veya mevcut
bir araca bayrak eklenir; manifest'e plaka + zaman yazilir ki Faz 3 altin
seti bunlari sorgu ile dogrulayabilsin.
"""
from __future__ import annotations

from datetime import timedelta

from .plates import random_plate
from .population import Population, VehicleSpec
from .rhythm import Visit, _time_of_day
from .rng import SynthRandom


def inject(rng: SynthRandom, pop: Population, visits: list[Visit]) -> dict:
    r = rng.for_stream("anomalies")
    mid = pop.period_start + (pop.period_end - pop.period_start) / 2
    manifest: dict = {}

    # 1. Uc gun (3 gece) kalan misafir.
    three = VehicleSpec(
        plate=random_plate(r), kind="guest", person_name="Uzun Konaklama",
        room_no="512", registered=True,
        reg_from=pop.period_start - timedelta(days=1),
        reg_to=pop.period_end + timedelta(days=1),
        anomaly="three_day_stay",
    )
    pop.vehicles.append(three)
    entry = _time_of_day(mid, 15.0, r)
    leave = _time_of_day(mid + timedelta(days=3), 11.0, r)
    visits.append(Visit(three, entry, leave))
    manifest["three_day_stay"] = {
        "plate": three.plate, "entry_ts": entry.isoformat(), "exit_ts": leave.isoformat(),
        "nights": 3,
    }

    # 2. Bes gece ust uste gelen kayitsiz arac.
    recurring = VehicleSpec(
        plate=random_plate(r), kind="unknown", known=False,
        anomaly="recurring_unregistered",
    )
    pop.vehicles.append(recurring)
    span = (pop.period_end - pop.period_start).days
    start_day = pop.period_start + timedelta(days=int(span * 0.3))
    nights = []
    for i in range(5):
        d = start_day + timedelta(days=i)
        e = _time_of_day(d, 21.0 + r.random(), r)
        x = _time_of_day(d + timedelta(days=1), 6.0 + r.random(), r)
        visits.append(Visit(recurring, e, x))
        nights.append(e.isoformat())
    manifest["recurring_unregistered"] = {"plate": recurring.plate, "nights": nights}

    # 3. 03:00 girisi (alisilmadik saat).
    night = VehicleSpec(
        plate=random_plate(r), kind="unknown", known=False, anomaly="night_entry"
    )
    pop.vehicles.append(night)
    d = pop.period_start + timedelta(days=int((pop.period_end - pop.period_start).days * 0.6))
    e = d.replace(hour=3, minute=r.randint(0, 40), second=r.randint(0, 59), microsecond=0)
    x = e + timedelta(hours=r.randint(1, 4))
    visits.append(Visit(night, e, x))
    manifest["night_entry"] = {"plate": night.plate, "entry_ts": e.isoformat()}

    # 4. Kara listedeki plaka - mevcut bir bilinmeyene bayrak.
    unknowns = [v for v in pop.by_kind("unknown") if v.anomaly is None and not v.synthetic]
    blk = unknowns[0] if unknowns else pop.vehicles[0]
    blk.is_blacklisted = True
    blk.anomaly = "blacklisted"  # rhythm zaten calisti; olaylari kirden muaf tutulur
    appears = sorted(v.entry_ts for v in visits if v.spec is blk)
    if not appears:
        d = _time_of_day(mid + timedelta(days=1), 19.0, r)
        visits.append(Visit(blk, d, d + timedelta(hours=2)))
        appears = [d]
    manifest["blacklisted"] = {
        "plate": blk.plate,
        "first_seen": appears[0].isoformat(),
        "appearances": len(appears),
    }

    visits.sort(key=lambda v: v.entry_ts)
    return manifest
