#!/usr/bin/env python3
"""Public demo icin sabit, kuratorlu sentetik veri.

Faz 8c demosundaki 6 senaryo plakasi + oneri sorularinin hepsinin gercek bir
cevabi olsun diye events / sessions / notes tablolarini elle doldurur.
`scripts/synth.py`den farki: rastgele degil, senaryo kartlariyla birebir
hizali ve ingest API'sine ihtiyac duymadan dogrudan DB'ye yazar.

Kullanim (konteyner icinde):
    python scripts/seed_demo.py            # reset + seed
    python scripts/seed_demo.py --keep     # mevcut demo verisini silme, ustune ekle

Idempotent: --keep verilmezse once events/sessions/notes TRUNCATE edilir ve
[DEMO] etiketli arac/kisi kayitlari silinir.
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, text

from kervansaray.db import session_scope
from kervansaray.db.models import (
    Direction,
    Event,
    MatchStatus,
    Note,
    Person,
    PersonKind,
    Registration,
    Session,
    Vehicle,
)
from kervansaray.text.plates import canonicalize

UTC = timezone.utc
NOW = datetime.now(UTC)
APR15 = datetime(2026, 4, 15, tzinfo=UTC)

DEVICE = "jetson-orin-01"
MODEL = "yolo-plate-v3"
CAM_IN = "cam-nizamiye-giris"
CAM_OUT = "cam-nizamiye-cikis"

_track = iter(range(100_000, 999_999))


# --- olay/oturum uretimi --------------------------------------------------

def _event(sess, *, plate, ts, direction, vehicle_id, match_status, camera):
    canon = canonicalize(plate)
    ev = Event(
        event_id=str(uuid4()),
        schema_version="1.0",
        device_id=DEVICE,
        camera_id=camera,
        ts=ts,
        raw_plate=plate,
        canonical_plate=canon,
        plate_confidence=round(random.uniform(0.90, 0.99), 3),
        direction=direction,
        track_id=next(_track),
        crop_ref=None,
        model_version=MODEL,
        vehicle_id=vehicle_id,
        match_status=match_status,
        match_score=100.0 if match_status == MatchStatus.exact else None,
        candidate_vehicle_id=None,
    )
    sess.add(ev)
    sess.flush()
    return ev


def visit(sess, *, plate, entry, exit_=None, vehicle_id=None,
          match_status=MatchStatus.unmatched):
    """Bir giris (+opsiyonel cikis) olayi ve karsilik gelen session'i yazar."""
    canon = canonicalize(plate)
    ev_in = _event(sess, plate=plate, ts=entry, direction=Direction.entry,
                   vehicle_id=vehicle_id, match_status=match_status, camera=CAM_IN)
    ev_out = None
    if exit_ is not None:
        ev_out = _event(sess, plate=plate, ts=exit_, direction=Direction.exit,
                        vehicle_id=vehicle_id, match_status=match_status, camera=CAM_OUT)
    sess.add(Session(
        vehicle_id=vehicle_id,
        canonical_plate=canon,
        entry_event_id=ev_in.id,
        exit_event_id=ev_out.id if ev_out else None,
        entry_ts=entry,
        exit_ts=exit_,
        duration_seconds=int((exit_ - entry).total_seconds()) if exit_ else None,
        missing_entry=False,
        missing_exit=False,
    ))


DEMO_PLATES = [
    "26ABC2626", "06AK0052", "34KAY44", "26XYZ413", "06XYZ01", "34VIP99",
]


def _mk_person(sess, name, kind, room=None, contact=None, title=None):
    p = Person(name=name, kind=kind, room_no=room, contact=contact, title=title)
    sess.add(p)
    sess.flush()
    return p


def _mk_vehicle(sess, plate, person, label, *, blacklisted=False, reg_from=None, reg_to=None):
    v = Vehicle(plate=canonicalize(plate), person_id=person.id if person else None,
                label=label, is_blacklisted=blacklisted)
    sess.add(v)
    sess.flush()
    if person and reg_from is not None:
        sess.add(Registration(vehicle_id=v.id, person_id=person.id,
                              valid_from=reg_from, valid_to=reg_to))
    return v


def _weekday_series(start, end, weekdays, hour, minute=0):
    d = start
    while d < end:
        if d.weekday() in weekdays:
            yield d.replace(hour=hour, minute=minute, second=0, microsecond=0)
        d += timedelta(days=1)


# --- demo senaryolari ----------------------------------------------------

def seed_scenarios(sess):
    # 1) 26 ABC 2626 - Guvenlik Muduru: sik giren, su an sahada
    p = _mk_person(sess, "Tarık Akkaya", PersonKind.staff, contact="guvenlik.amiri@kervansaray.local",
                   title="Güvenlik Müdürü")
    v = _mk_vehicle(sess, "26 ABC 2626", p, "Guvenlik Muduru - Nizamiye",
                    reg_from=NOW - timedelta(days=400), reg_to=None)
    # Nisan 15 + Haziran/Temmuz seyrek + son 4 hafta Pzt/Car/Cum
    visit(sess, plate="26 ABC 2626", entry=APR15.replace(hour=8, minute=25),
          exit_=APR15.replace(hour=18, minute=40), vehicle_id=v.id, match_status=MatchStatus.exact)
    for wk in (10, 7, 4):  # haftalar once, birer gun
        d = NOW - timedelta(weeks=wk)
        visit(sess, plate="26 ABC 2626", entry=d.replace(hour=9, minute=5),
              exit_=d.replace(hour=17, minute=50), vehicle_id=v.id, match_status=MatchStatus.exact)
    for day in _weekday_series(NOW - timedelta(days=26), NOW - timedelta(days=1),
                               {0, 2, 4}, 8, 30):
        visit(sess, plate="26 ABC 2626", entry=day,
              exit_=day.replace(hour=18, minute=random.randint(0, 55)),
              vehicle_id=v.id, match_status=MatchStatus.exact)
    # bugun girdi, henuz cikmadi -> occupancy + "bu ay"
    visit(sess, plate="26 ABC 2626", entry=NOW - timedelta(hours=3),
          exit_=None, vehicle_id=v.id, match_status=MatchStatus.exact)

    # 2) 06 AK 0052 - Kayitli Misafir: ayda ~1 ziyaret
    p = _mk_person(sess, "Can Ozturk", PersonKind.guest, contact="(0532) 111 22 33",
                   title="İş Ortağı")
    v = _mk_vehicle(sess, "06 AK 0052", p, "Kayitli Misafir - Is Ortagi",
                    reg_from=NOW - timedelta(days=200), reg_to=NOW + timedelta(days=160))
    for d in (APR15, datetime(2026, 5, 20, tzinfo=UTC), datetime(2026, 6, 18, tzinfo=UTC),
              datetime(2026, 7, 22, tzinfo=UTC), datetime(2026, 8, 14, tzinfo=UTC),
              datetime(2026, 9, 3, tzinfo=UTC)):
        visit(sess, plate="06 AK 0052", entry=d.replace(hour=10, minute=15),
              exit_=d.replace(hour=15, minute=30), vehicle_id=v.id, match_status=MatchStatus.exact)

    # 3) 34 KAY 44 - VIP Misafir: nadir, protokol
    p = _mk_person(sess, "Sn. Kaya", PersonKind.guest, room="Baskanlik Suiti", contact="kaya@holding.com.tr",
                   title="VIP Protokol Misafiri")
    v = _mk_vehicle(sess, "34 KAY 44", p, "VIP Misafir - Protokol",
                    reg_from=NOW - timedelta(days=300), reg_to=None)
    for d in (APR15, datetime(2026, 7, 10, tzinfo=UTC), datetime(2026, 9, 5, tzinfo=UTC)):
        visit(sess, plate="34 KAY 44", entry=d.replace(hour=11, minute=0),
              exit_=d.replace(hour=13, minute=20), vehicle_id=v.id, match_status=MatchStatus.exact)

    # 4) 34 VIP 99 - Kara Liste: nizamiyeden geri cevrildi
    p = _mk_person(sess, "Hacizli Arac", PersonKind.guest, contact="guvenlik@kervansaray.com")
    v = _mk_vehicle(sess, "34 VIP 99", p, "Hacizli / Kara Liste - Giris Yasagi",
                    blacklisted=True, reg_from=None)
    for d in (APR15, datetime(2026, 8, 28, tzinfo=UTC)):
        visit(sess, plate="34 VIP 99", entry=d.replace(hour=16, minute=5),
              exit_=d.replace(hour=16, minute=22), vehicle_id=v.id, match_status=MatchStatus.exact)

    # 5) 06 XYZ 01 - Overstay: 3+ gundur sahada, cikis yok
    visit(sess, plate="06 XYZ 01", entry=NOW - timedelta(days=3, hours=4),
          exit_=None, vehicle_id=None, match_status=MatchStatus.unmatched)

    # 6) 26 XYZ 413 - Kayitsiz, tekrarlayan + bir gece girisi
    for d, h, m in ((datetime(2026, 8, 20, tzinfo=UTC), 9, 0),
                    (datetime(2026, 8, 27, tzinfo=UTC), 10, 30),
                    (datetime(2026, 9, 1, tzinfo=UTC), 8, 45),
                    (datetime(2026, 9, 4, tzinfo=UTC), 0, 15),   # 03:15 Istanbul -> gece girisi
                    (datetime(2026, 9, 8, tzinfo=UTC), 11, 0)):
        e = d.replace(hour=h, minute=m)
        visit(sess, plate="26 XYZ 413", entry=e, exit_=e + timedelta(hours=2, minutes=20),
              vehicle_id=None, match_status=MatchStatus.unmatched)


def seed_background(sess, n_vehicles=32):
    """Mevcut populasyondan rastgele araclarla arka plan trafigi."""
    rng = random.Random(8642)
    pool = list(sess.execute(
        select(Vehicle.id, Vehicle.plate)
        .where(Vehicle.plate.notin_(DEMO_PLATES))
        .where(Vehicle.id.in_(select(Registration.vehicle_id)))
    ).all())
    rng.shuffle(pool)
    inside = 0
    for vid, plate in pool[:n_vehicles]:
        for _ in range(rng.randint(1, 4)):
            day = APR15 if rng.random() < 0.18 else NOW - timedelta(days=rng.randint(1, 150))
            entry = day.replace(hour=rng.randint(7, 20), minute=rng.choice([0, 15, 30, 45]),
                                second=0, microsecond=0)
            leave_open = inside < 4 and rng.random() < 0.10 and entry > NOW - timedelta(days=2)
            if leave_open:
                inside += 1
                visit(sess, plate=plate, entry=entry, exit_=None,
                      vehicle_id=vid, match_status=MatchStatus.exact)
            else:
                dur = timedelta(hours=rng.randint(1, 9), minutes=rng.choice([0, 20, 40]))
                exit_ = min(entry + dur, NOW - timedelta(minutes=5))
                if exit_ <= entry:
                    exit_ = entry + timedelta(hours=1)
                # ~%8 kacirilmis cikis (S8 kir)
                if rng.random() < 0.08:
                    ev_in = _event(sess, plate=plate, ts=entry, direction=Direction.entry,
                                   vehicle_id=vid, match_status=MatchStatus.exact, camera=CAM_IN)
                    sess.add(Session(vehicle_id=vid, canonical_plate=canonicalize(plate),
                                     entry_event_id=ev_in.id, exit_event_id=None,
                                     entry_ts=entry, exit_ts=None, duration_seconds=None,
                                     missing_entry=False, missing_exit=True))
                else:
                    visit(sess, plate=plate, entry=entry, exit_=exit_,
                          vehicle_id=vid, match_status=MatchStatus.exact)


NOTES = [
    ("Guvenlik Amirligi", -170,
     "PROSEDUR - VIP misafir araci: Nizamiyede bekletilmez. Vale ve protokol "
     "gorevlisi cagrilir, arac Dogu Otoparki A-01 rezervasyonlu alana yonlendirilir. "
     "Kayit bilgisi eksikse amir onayi ile gecici gecis verilir."),
    ("Nobetci Amir", -140,
     "PROSEDUR - Kayitsiz / yabanci arac: Surucu kimligi ve ziyaret sebebi kaydedilir, "
     "ilgili birime telefonla teyit alinir. Teyit yoksa giris verilmez, ziyaretci "
     "otoparki disinda bekletilir. Kargo/tedarik araclari icin sevkiyat evraki istenir."),
    ("Hukuk Birimi", -120,
     "PROSEDUR - Kara liste / hacizli arac: Sistemde kara liste alarmi veren plaka "
     "tesise ALINMAZ. Bariyer acilmaz, arac geri cevrilir ve durum nobetci amire "
     "bildirilir. Israr halinde kolluk kuvveti bilgilendirilir. Karar No 2026/41."),
    ("Devriye Ekibi", -80,
     "PROSEDUR - Gece girisi (saat 00:00-05:00): Bu saatlerde giris yapan tum araclar "
     "icin devriye ekibi otoparka yonlendirilir, arac ve surucu fiziki kontrol edilir. "
     "Supheli durum tutanakla kayit altina alinir."),
    ("Otopark Sefligi", -45,
     "PROSEDUR - 48 saat overstay: Sahada 48 saatten uzun kalan arac 'terk arac suphesi' "
     "olarak isaretlenir. Plaka sahibine ulasilir; 24 saat icinde cevap yoksa arac "
     "cekiciyle kapali otoparka alinir ve ihlal tutanagi duzenlenir."),
    ("Guvenlik Amirligi", -10,
     "VARDIYA NOTU - Nizamiye giris bariyeri sabah 07:00-09:00 arasi yogun. Personel ve "
     "kayitli misafir plakalari otomatik geciyor; kayitsiz araclarda kuyruk olusuyor, "
     "ikinci gorevli yonlendiriliyor."),
]


def seed_notes(sess):
    for author, days_ago, body in NOTES:
        sess.add(Note(ts=NOW + timedelta(days=days_ago), author=author, body=body))


def reset(sess):
    sess.execute(text("TRUNCATE events, sessions, notes RESTART IDENTITY CASCADE"))
    # Demo araclarini/kisilerini sabit plaka listesinden temizle (arka plan
    # populasyonuna dokunmadan).
    rows = list(sess.execute(
        select(Vehicle.id, Vehicle.person_id).where(Vehicle.plate.in_(DEMO_PLATES))
    ).all())
    if rows:
        vids = [r.id for r in rows]
        pids = [r.person_id for r in rows if r.person_id]
        sess.execute(delete(Registration).where(Registration.vehicle_id.in_(vids)))
        sess.execute(delete(Vehicle).where(Vehicle.id.in_(vids)))
        if pids:
            sess.execute(delete(Person).where(Person.id.in_(pids)))


def main():
    ap = argparse.ArgumentParser(description="Kervansaray public demo seed")
    ap.add_argument("--keep", action="store_true", help="mevcut demo verisini silme")
    args = ap.parse_args()

    with session_scope() as sess:
        if not args.keep:
            reset(sess)
        seed_scenarios(sess)
        seed_background(sess)
        seed_notes(sess)
        sess.flush()
        ev = sess.scalar(select(func.count()).select_from(Event))
        se = sess.scalar(select(func.count()).select_from(Session))
        no = sess.scalar(select(func.count()).select_from(Note))
        inside = sess.scalar(text(
            "SELECT count(*) FROM (SELECT DISTINCT ON (plate) direction FROM v_events "
            "ORDER BY plate, ts DESC, (direction='exit') DESC) t WHERE direction='entry'"
        ))
        print(f"seed tamam: events={ev} sessions={se} notes={no} · su an sahada≈{inside}")


if __name__ == "__main__":
    main()
