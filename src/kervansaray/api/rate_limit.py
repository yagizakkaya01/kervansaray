"""In-memory IP rate limiter (Ponytail: saf stdlib, sifir dis bagimlilik).

Sliding window algoritmasi ile tek process / thread-safe calisir.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict


def _env_int(name: str, default: int) -> int:
    try:
        val = os.environ.get(name)
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


class RateLimiter:
    def __init__(self, per_minute: int | None = None, per_day: int | None = None):
        self.per_minute = per_minute if per_minute is not None else _env_int("RATE_LIMIT_PER_MINUTE", 10)
        self.per_day = per_day if per_day is not None else _env_int("RATE_LIMIT_PER_DAY", 500)
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> tuple[bool, str | None]:
        """Istemci IP'sinin istek kotasini kontrol eder.

        (allowed, error_message) dondurur.
        """
        if os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
            return True, None

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
                    f"Dakikalık soru limitine ({self.per_minute} soru/dk) ulaştınız. Lütfen 1 dakika bekleyin veya kotayı sıfırlayın.",
                )

            if len(recent) >= self.per_day:
                return (
                    False,
                    f"Günlük soru limitine ({self.per_day} soru/gün) ulaştınız. Test modunda kotayı sıfırlayabilirsiniz.",
                )

            recent.append(now)
            return True, None

    def clear(self) -> None:
        """Tum IP gecmisini sifirlar (yalniz testler icin)."""
        with self._lock:
            self._requests.clear()

    def clear_ip(self, client_ip: str) -> None:
        """Yalniz bir IP'nin kota gecmisini sifirlar (public 'kotami sifirla')."""
        with self._lock:
            self._requests.pop(client_ip, None)


limiter = RateLimiter()
