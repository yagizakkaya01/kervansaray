"""Standart Python loglama yapilandirmasi."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from .config import settings

log = logging.getLogger("kervansaray")

_NOISY = (
    "urllib3", "requests", "werkzeug",
)


def setup_logging() -> None:
    """Python standart logging yapilandirmasi: konsol + opsiyonel dosya."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")

    handlers: list[logging.Handler] = []
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    handlers.append(sh)

    if settings.LOG_TO_FILE:
        os.makedirs(os.path.dirname(settings.LOG_FILE) or ".", exist_ok=True)
        fh = RotatingFileHandler(
            settings.LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        handlers.append(fh)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    for lib in _NOISY:
        logging.getLogger(lib).setLevel(logging.WARNING)

    log.info("Logging initialized (level=%s, file=%s)", settings.LOG_LEVEL, settings.LOG_FILE)
