"""Bildirimler: deterministik kural motoru, bellek-içi broker ve SSE dağıtıcısı (ROADMAP Faz 7).

PROJECT_BRIEF §3.7:
  - Her gelen olayı değerlendiren deterministik kural motoru.
  - LLM asla tetikleyici değildir; tetikleme %100 Python kurallarıyla çalışır.
  - Kurallar: kara liste (blacklist), kayıtsız araç (unregistered), misafir gelişi (guest_arrival),
    gece girişi (night_entry), inceleme bekleyen (pending), süre aşımı (overstay).

Ponytail:
  - Sıfır harici kuyruk/mesajlaşma kütüphanesi (Redis/Celery/RabbitMQ yok).
  - Standart kütüphane: queue.Queue + collections.deque + threading.Lock.
"""
from __future__ import annotations

import collections
import dataclasses
import json
import queue
import threading
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from kervansaray.db.models import Direction, Event, MatchStatus, PersonKind, Session
from kervansaray.logging import log

# Türkiye yerel saat dilimi (UTC+3)
TR = timezone(timedelta(hours=3))


# Eşikler
OVERSTAY_SECONDS = 48 * 3600  # 48 saat
NIGHT_START_HOUR = 0
NIGHT_END_HOUR = 5


@dataclasses.dataclass(frozen=True)
class Notification:
    id: str
    rule: str
    severity: str  # "critical" | "warning" | "info"
    plate: str
    title: str
    message: str
    ts: str  # ISO-8601
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_sse_data(self) -> str:
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class NotificationBroker:
    """Tek işlem içi, thread-safe bildirim broker'ı (Ponytail: zero-broker)."""

    def __init__(self, history_limit: int = 100) -> None:
        self._history: collections.deque[Notification] = collections.deque(maxlen=history_limit)
        self._subscribers: set[queue.Queue[Notification]] = set()
        self._lock = threading.Lock()

    def publish(self, notification: Notification) -> None:
        with self._lock:
            self._history.append(notification)
            dead: list[queue.Queue[Notification]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(notification)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.discard(q)
        log.info(
            "Notification published rule=%s severity=%s plate=%s",
            notification.rule, notification.severity, notification.plate,
        )

    def subscribe(self, maxsize: int = 50) -> queue.Queue[Notification]:
        q: queue.Queue[Notification] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[Notification]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)[-limit:]
            items.reverse()
            return [item.to_dict() for item in items]

    def clear(self) -> None:
        """Test amaçlı sıfırlama."""
        with self._lock:
            self._history.clear()
            self._subscribers.clear()


# Global Singleton Broker
broker = NotificationBroker()


def evaluate_event(db: DbSession, event: Event) -> list[Notification]:
    """Ingest edilen bir olayı analiz eder ve tetiklenen kurallar için bildirim üretir.

    Asla LLM çağırmaz; kurallar %100 deterministiktir.
    """
    notifications: list[Notification] = []
    now_iso = datetime.now(UTC).isoformat()
    plate = event.canonical_plate or event.raw_plate

    # 1. Kara Liste Alarmı (En yüksek öncelik: CRITICAL)
    if event.vehicle and event.vehicle.is_blacklisted:
        notifications.append(
            Notification(
                id=uuid4().hex,
                rule="blacklist",
                severity="critical",
                plate=plate,
                title=f"KARA LİSTE ALARMI: {plate}",
                message=(
                    f"Kara listedeki {plate} plakalı araç kapıda tespit edildi! "
                    f"Yön: {event.direction.value.upper()}."
                ),
                ts=now_iso,
                metadata={
                    "event_id": event.event_id,
                    "direction": event.direction.value,
                    "camera_id": event.camera_id,
                    "vehicle_id": event.vehicle_id,
                },
            )
        )

    # 2. Kayıtsız Araç Girişi (WARNING)
    if event.match_status == MatchStatus.unmatched and event.direction == Direction.entry:
        notifications.append(
            Notification(
                id=uuid4().hex,
                rule="unregistered",
                severity="warning",
                plate=plate,
                title=f"Kayıtsız Araç Girişi: {plate}",
                message=(
                    f"{plate} plakalı araç için tescil kaydı bulunamadı. "
                    "Güvenlik teyidi gerekebilir."
                ),
                ts=now_iso,
                metadata={
                    "event_id": event.event_id,
                    "direction": event.direction.value,
                    "camera_id": event.camera_id,
                },
            )
        )

    # 3. İnceleme Bekleyen Bulanık Plaka (WARNING)
    if event.match_status == MatchStatus.pending:
        notifications.append(
            Notification(
                id=uuid4().hex,
                rule="pending_review",
                severity="warning",
                plate=plate,
                title=f"Plaka Onayı Bekliyor: {event.raw_plate}",
                message=(
                    f"Kamera '{event.raw_plate}' okudu, sistem '{plate}' olarak aday gösterdi. "
                    "Operatör onayı bekleniyor."
                ),
                ts=now_iso,
                metadata={
                    "event_id": event.event_id,
                    "raw_plate": event.raw_plate,
                    "candidate_plate": plate,
                    "candidate_vehicle_id": event.candidate_vehicle_id,
                },
            )
        )

    # 4. Kayıtlı Misafir Gelişi (INFO / VIP Karşılama)
    if (
        event.direction == Direction.entry
        and event.vehicle
        and event.vehicle.person
        and event.vehicle.person.kind == PersonKind.guest
    ):
        person = event.vehicle.person
        room_info = f" (Oda: {person.room_no})" if person.room_no else ""
        notifications.append(
            Notification(
                id=uuid4().hex,
                rule="guest_arrival",
                severity="info",
                plate=plate,
                title=f"Kayıtlı Misafir Geldi: {person.name}",
                message=(
                    f"Misafirimiz {person.name}{room_info} {plate} plakalı araçla "
                    "tesise giriş yaptı."
                ),
                ts=now_iso,
                metadata={
                    "event_id": event.event_id,
                    "person_id": person.id,
                    "person_name": person.name,
                    "room_no": person.room_no,
                },
            )
        )

    # 5. Gece Girişi (INFO)
    # Türkiye yerel saatine (UTC+3) göre kontrol
    if event.ts:
        ts_aware = event.ts if event.ts.tzinfo else event.ts.replace(tzinfo=TR)
        event_hour = ts_aware.astimezone(TR).hour
    else:
        event_hour = 0
    if event.direction == Direction.entry and NIGHT_START_HOUR <= event_hour < NIGHT_END_HOUR:
        notifications.append(
            Notification(
                id=uuid4().hex,
                rule="night_entry",
                severity="info",
                plate=plate,
                title=f"Gece Girişi: {plate}",
                message=(
                    f"{plate} plakalı araç saat {event_hour:02d}:00 "
                    "civarında gece girişi yaptı."
                ),
                ts=now_iso,
                metadata={
                    "event_id": event.event_id,
                    "hour": event_hour,
                },
            )
        )

    # 6. Süre Aşımı (Overstay - WARNING)
    # Araç çıkış yaptığında toplam park süresi kontrol edilir
    if event.direction == Direction.exit:
        sess = db.scalar(
            select(Session).where(Session.exit_event_id == event.id).limit(1)
        )
        if sess and sess.duration_seconds and sess.duration_seconds > OVERSTAY_SECONDS:
            hours = round(sess.duration_seconds / 3600, 1)
            notifications.append(
                Notification(
                    id=uuid4().hex,
                    rule="overstay",
                    severity="warning",
                    plate=plate,
                    title=f"Süre Aşımı (Overstay): {plate}",
                    message=(
                        f"{plate} plakalı araç {hours} saat tesiste kalarak "
                        "izin verilen süreyi aştı."
                    ),
                    ts=now_iso,
                    metadata={
                        "event_id": event.event_id,
                        "session_id": sess.id,
                        "duration_hours": hours,
                    },
                )
            )

    return notifications
