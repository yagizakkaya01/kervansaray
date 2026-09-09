"""Public demo (read-only) korumalari.

PROJECT_BRIEF S12/S24: public demo KESINLIKLE read-only. DB'ye yazan veya
durum degistiren (tescil upsert, demo reset, rate-limit reset) uclar bu
dekoratorle korunur; `ENABLE_OPERATOR_ROUTES=false` iken 403 doner.

`routes_events.post_event` ayni kontrolu inline yapiyor; yeni yazma uclari
icin tek kaynak burasi.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify


def operator_only(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Yalnizca operator modunda calisir; public demoda 403."""

    @wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        from kervansaray.config import settings

        if not settings.ENABLE_OPERATOR_ROUTES:
            return (
                jsonify({
                    "ok": False,
                    "error": (
                        "Bu islem public demo modunda devre disidir "
                        "(yalnizca operator). Demoyu sifirlamak icin "
                        "konteyneri yeniden baslatin."
                    ),
                }),
                403,
            )
        return fn(*args, **kwargs)

    return _wrapped
