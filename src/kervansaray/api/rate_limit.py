"""In-memory IP rate limiter (Ponytail: saf stdlib, sifir dis bagimlilik).

Sliding window algoritmasi ile tek process / thread-safe calisir.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, per_minute: int = 5, per_day: int = 20):
        self.per_minute = per_minute
        self.per_day = per_day
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> tuple[bool, str | None]:
        """Istemci IP'sinin istek kotasini kontrol eder.

        (allowed, error_message) dondurur.
        """
        now = time.time()
        minute_ago = now - 60.0
        day_ago = now - 86400.0

        with self._lock:
            history = self._requests[client_ip]
            # 24 saatten eski kayitlari temizle (bellek sizintisi onleme)
            self._requests[client_ip] = [t for t in history if t > day_ago]
            recent = self._requests[client_ip]

            minute_count = sum(1 for t in recent if t > minute_ago)
            if minute_count >= self.per_minute:
                return (
                    False,
                    "Dakikalık soru limitine (5 soru/dk) ulaştınız. Lütfen 1 dakika bekleyin.",
                )

            if len(recent) >= self.per_day:
                return (
                    False,
                    "Günlük soru limitine (20 soru/gün) ulaştınız. Yarın tekrar deneyebilirsiniz.",
                )

            recent.append(now)
            return True, None

    def clear(self) -> None:
        """Testler icin hafizayi sifirlar."""
        with self._lock:
            self._requests.clear()


limiter = RateLimiter(per_minute=5, per_day=20)
