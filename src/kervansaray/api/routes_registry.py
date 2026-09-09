"""Araç tescil yönetimi ve demo sıfırlama API'si (PROJECT_BRIEF S3.2 / S8).

- GET  /api/registry        : Sistemdeki tescilli ve senaryo araçlarını listeler
- POST /api/registry/upsert : Araç kaydını oluşturur veya günceller (DB'ye yazar)
- POST /api/demo/reset      : Demo veritabanını ve senaryoları fabrika ayarlarına sıfırlar
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from flask import Blueprint, jsonify, request
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import joinedload

from kervansaray.db import session_scope
from kervansaray.db.models import (
    Event,
    MatchStatus,
    Person,
    PersonKind,
    Registration,
    Vehicle,
)
from kervansaray.query_pipeline import query_cache
from kervansaray.text.plates import canonicalize

bp = Blueprint("registry", __name__, url_prefix="/api")
log = logging.getLogger(__name__)

UTC = timezone.utc

# 6 Demo Senaryo Plakası
DEMO_SCENARIO_PLATES = [
    {"plate": "26 ABC 2626", "default_name": "H. Aydın (Güvenlik Müdürü)", "default_kind": "manager", "default_addr": "Güvenlik Amirliği", "default_contact": "guvenlik.amiri@kervansaray.local"},
    {"plate": "06 AK 0052", "default_name": "Can Öztürk", "default_kind": "guest", "default_addr": "İş Ortağı • Doğu Otoparkı", "default_contact": "(0532) 111 22 33"},
    {"plate": "34 KAY 44", "default_name": "Sayın Kaya", "default_kind": "vip", "default_addr": "Başkanlık Süiti", "default_contact": "kaya@holding.com.tr"},
    {"plate": "26 XYZ 413", "default_name": "Kayıt Yok (Kargo / Tedarik)", "default_kind": "unregistered", "default_addr": "Geçici Misafir", "default_contact": "—"},
    {"plate": "06 XYZ 01", "default_name": "Terk Araç Şüphesi", "default_kind": "warning", "default_addr": "B Blok Kapalı Otopark", "default_contact": "—"},
    {"plate": "34 VIP 99", "default_name": "Yasaklı Araç", "default_kind": "blacklist", "default_addr": "Hukuk Birimi (Hacizli)", "default_contact": "guvenlik@kervansaray.com"},
]


@bp.get("/registry")
def list_registry() -> Any:
    """Tescil listesini veritabanından çeker."""
    try:
        with session_scope() as sess:
            # DB'deki tüm araçları kişi bilgisiyle yükle
            vehicles = list(
                sess.scalars(
                    select(Vehicle)
                    .options(joinedload(Vehicle.person))
                    .order_by(Vehicle.id.asc())
                ).unique()
            )
            v_map = {v.plate: v for v in vehicles}

            results = []
            seen_plates = set()

            # Önce 6 ana demo senaryo plakasını garantile
            for idx, item in enumerate(DEMO_SCENARIO_PLATES, 1):
                canon = canonicalize(item["plate"])
                seen_plates.add(canon)
                v = v_map.get(canon)

                if v and v.person:
                    kind = str(v.person.kind.value)
                    lbl = (v.label or "").lower()
                    if v.is_blacklisted:
                        kind = "blacklist"
                    elif any(w in lbl for w in ("guvenlik", "güvenlik", "manager", "amir")):
                        kind = "manager"
                    elif any(w in lbl for w in ("vip", "protokol", "baskan", "başkan")):
                        kind = "vip"
                    elif any(w in lbl for w in ("terk", "warning", "şüphe", "suphe")):
                        kind = "warning"

                    contact_val = v.person.contact if v.person.contact is not None else item["default_contact"]
                    results.append({
                        "id": idx,
                        "plate": item["plate"],
                        "name": v.person.name,
                        "kind": kind,
                        "address": v.label or item["default_addr"],
                        "contact": contact_val,
                        "is_blacklisted": bool(v.is_blacklisted),
                    })
                elif v:
                    kind = "blacklist" if v.is_blacklisted else item["default_kind"]
                    results.append({
                        "id": idx,
                        "plate": item["plate"],
                        "name": v.label or item["default_name"],
                        "kind": kind,
                        "address": v.label or item["default_addr"],
                        "contact": item["default_contact"],
                        "is_blacklisted": bool(v.is_blacklisted),
                    })
                else:
                    results.append({
                        "id": idx,
                        "plate": item["plate"],
                        "name": item["default_name"],
                        "kind": item["default_kind"],
                        "address": item["default_addr"],
                        "contact": item["default_contact"],
                        "is_blacklisted": item["default_kind"] == "blacklist",
                    })

            return jsonify({"ok": True, "registry": results}), 200

    except Exception as exc:  # noqa: BLE001
        log.exception("Registry listeleme hatasi")
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.post("/registry/upsert")
def upsert_registry() -> Any:
    """Aracı DB'ye kaydeder veya günceller."""
    data = request.get_json(silent=True) or {}
    raw_plate = (data.get("plate") or "").strip().upper()
    if not raw_plate:
        return jsonify({"ok": False, "error": "Plaka zorunludur."}), 400

    canon = canonicalize(raw_plate)
    name = (data.get("name") or "").strip()
    kind = (data.get("kind") or "guest").strip().lower()
    address = (data.get("address") or "").strip()
    contact = (data.get("contact") or "").strip()

    try:
        with session_scope() as sess:
            vehicle = sess.scalar(
                select(Vehicle).options(joinedload(Vehicle.person)).where(Vehicle.plate == canon)
            )

            if kind == "unregistered":
                # Kayıtsız yap: vehicle varsa sil veya person bağını kaldır
                if vehicle:
                    sess.execute(delete(Registration).where(Registration.vehicle_id == vehicle.id))
                    sess.execute(update(Event).where(Event.vehicle_id == vehicle.id).values(vehicle_id=None, match_status=MatchStatus.unmatched))
                    p_id = vehicle.person_id
                    sess.delete(vehicle)
                    if p_id:
                        p = sess.get(Person, p_id)
                        if p:
                            sess.delete(p)
                sess.flush()
            else:
                is_bl = (kind == "blacklist")

                # Person oluştur/güncelle
                p_kind = PersonKind.guest
                if kind in ("manager", "staff"):
                    p_kind = PersonKind.staff
                elif kind == "vendor":
                    p_kind = PersonKind.vendor

                if vehicle and vehicle.person:
                    person = vehicle.person
                    person.name = name or vehicle.person.name
                    person.kind = p_kind
                    if "contact" in data:
                        person.contact = contact or None
                else:
                    person = Person(
                        name=name or f"Tescilli Sürücü ({raw_plate})",
                        kind=p_kind,
                        contact=contact or None,
                    )
                    sess.add(person)
                    sess.flush()

                # Vehicle oluştur/güncelle
                if not vehicle:
                    vehicle = Vehicle(
                        plate=canon,
                        person_id=person.id,
                        label=address or f"{name} ({kind})",
                        is_blacklisted=is_bl,
                    )
                    sess.add(vehicle)
                    sess.flush()
                else:
                    vehicle.person_id = person.id
                    if address:
                        vehicle.label = address
                    elif name:
                        vehicle.label = f"{name} - {kind.upper()}"
                    vehicle.is_blacklisted = is_bl
                    sess.flush()

                # Registration oluştur/güncelle
                reg = sess.scalar(select(Registration).where(Registration.vehicle_id == vehicle.id))
                if not reg:
                    reg = Registration(
                        vehicle_id=vehicle.id,
                        person_id=person.id,
                        valid_from=datetime.now(UTC) - timedelta(days=365),
                        valid_to=None,
                    )
                    sess.add(reg)
                else:
                    reg.person_id = person.id
                    reg.valid_to = None

                # İlgili tüm olayları bu araca bağla
                sess.execute(
                    update(Event)
                    .where(Event.canonical_plate == canon)
                    .values(
                        vehicle_id=vehicle.id,
                        match_status=MatchStatus.exact,
                    )
                )
                sess.flush()

        # Sorgu önbelleğini temizle (yeni tescil anında algılansın)
        query_cache.clear()

        return jsonify({
            "ok": True,
            "message": f"{raw_plate} tescili başarıyla güncellendi.",
            "record": {
                "plate": raw_plate,
                "name": name,
                "kind": kind,
                "address": address,
                "contact": contact,
            }
        }), 200

    except Exception as exc:  # noqa: BLE001
        log.exception("Registry upsert hatasi: %s", raw_plate)
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.post("/demo/reset")
def reset_demo() -> Any:
    """Demo veritabanını fabrika ayarlarına sıfırlar."""
    try:
        from scripts.seed_demo import reset, seed_background, seed_notes, seed_scenarios
        from kervansaray.demo_cache import warm as warm_cache

        with session_scope() as sess:
            reset(sess)
            seed_scenarios(sess)
            seed_background(sess)
            seed_notes(sess)
            sess.flush()
            warm_cache(sess)

        query_cache.clear()

        return jsonify({
            "ok": True,
            "message": "Demo veritabanı ve 6 senaryo verisi fabrika ayarlarına sıfırlandı."
        }), 200

    except Exception as exc:  # noqa: BLE001
        log.exception("Demo reset hatasi")
        return jsonify({"ok": False, "error": str(exc)}), 500
