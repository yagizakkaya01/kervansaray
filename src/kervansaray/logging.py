"""Yapilandirilmis loglama sistemi.

CILEKAI `core/logging.py`'den tasindi (PROJECT_BRIEF S13 - "observability
setup"). Korunan cekirdek: ANSI renkli, okunabilir konsol akisi + ayri
detayli dosya handler'i + gurultulu 3. parti kutuphanelerin susturulmasi.

CILEKAI'ye ozel pipeline metodlari (rag / rerank / faq / cache) cikarildi;
yerine bu projenin alanina uygun metodlar eklendi (event / query / tool /
alert).

Ornek konsol ciktisi:
    --- REQ #0001 --------------------------------------------------
    [14:32:07] QUERY  | "dun gece kimler girdi?" | user=operator
    [14:32:07] TOOL   | query_events(start=..., end=...) -> 3 satir (12ms)
    [14:32:07] LLM    | groq (640ms)
    [14:32:07] DONE   | 664ms toplam | tool:12 llm:640
    ---------------------------------------------------------------
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config import settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class Colors:
    RESET = "\033[0m"
    DIM = "\033[2m"
    GRAY = "\033[90m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    RED = "\033[91m"
    WHITE = "\033[97m"


_LV_COLOR = {
    "SYS": Colors.MAGENTA,
    "QUERY": Colors.CYAN,
    "EVENT": Colors.GREEN,
    "TOOL": Colors.BLUE,
    "LLM": Colors.YELLOW,
    "ALERT": Colors.RED,
    "WARN": Colors.YELLOW,
    "ERROR": Colors.RED,
    "DONE": Colors.WHITE,
    "INFO": Colors.DIM,
}

_SEP_W = 62


class KervansarayLogger:
    """Konsol: okunabilir akis.  Dosya: her sey (DEBUG dahil)."""

    def __init__(self) -> None:
        self.use_colors = True
        self._py_logger = logging.getLogger("kervansaray")
        self._req_counter = 0
        self._lock = threading.Lock()

    # -- formatlama --------------------------------------------------------
    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _c(self, text: str, color: str) -> str:
        return f"{color}{text}{Colors.RESET}" if self.use_colors else text

    def _fmt(self, level: str, msg: str) -> str:
        color = _LV_COLOR.get(level, Colors.DIM)
        ts = self._c(f"[{self._ts()}]", Colors.GRAY)
        lv = self._c(f"{level:6}", color)
        return f"{ts} {lv} | {msg}"

    def _to_file(self, msg: str) -> None:
        self._py_logger.debug(re.sub(r"\033\[[0-9;]*m", "", msg))

    def _emit(self, level: str, msg: str) -> None:
        line = self._fmt(level, msg)
        print(line, flush=True)
        self._to_file(line)

    # -- istek sinirlari --------------------------------------------------
    def _next_id(self) -> str:
        with self._lock:
            self._req_counter += 1
            return f"{self._req_counter:04d}"

    def request_start(self, query: str, user: str | None = None) -> str:
        rid = self._next_id()
        tag = f" REQ #{rid} "
        pad = max(0, _SEP_W - len(tag) - 3)
        sep = f"{'-' * 3}{tag}{'-' * pad}"
        print(self._c(sep, Colors.DIM), flush=True)
        self._to_file(sep)

        q_short = query if len(query) <= 80 else query[:80] + "..."
        parts = [f'"{q_short}"']
        if user:
            parts.append(f"user={user}")
        self._emit("QUERY", " | ".join(parts))
        return rid

    def request_end(self, timings: dict | None = None) -> None:
        if timings:
            total = timings.get("total", 0)
            detail = " ".join(
                f"{label}:{timings[key]:.0f}"
                for key, label in (("tool", "tool"), ("llm", "llm"), ("db", "db"))
                if timings.get(key)
            )
            msg = f"{total:.0f}ms toplam"
            if detail:
                msg += " | " + detail
            self._emit("DONE", msg)
        sep = "-" * _SEP_W
        print(self._c(sep, Colors.DIM), flush=True)
        self._to_file(sep)

    # -- alan metodlari --------------------------------------------------
    def sys(self, message: str) -> None:
        self._emit("SYS", message)

    def query(self, question: str, user: str | None = None) -> None:
        q_short = question if len(question) <= 80 else question[:80] + "..."
        parts = [f'"{q_short}"']
        if user:
            parts.append(f"user={user}")
        self._emit("QUERY", " | ".join(parts))

    def event(self, plate: str, direction: str, matched: str = "unmatched") -> None:
        """Gelen bir arac hareketi (ingest)."""
        self._emit("EVENT", f"{plate} {direction} | match={matched}")

    def tool(self, name: str, rows: int | None = None, time_ms: float = 0) -> None:
        """Bir tool cagrisi ve sonucu (PROJECT_BRIEF S3.2)."""
        parts = [name]
        if rows is not None:
            parts.append(f"-> {rows} satir")
        if time_ms:
            parts.append(f"({time_ms:.0f}ms)")
        self._emit("TOOL", " ".join(parts))

    def llm(self, provider: str, time_ms: float = 0, fallback: bool = False) -> None:
        msg = f"{provider} ({time_ms:.0f}ms)"
        if fallback:
            msg += " [fallback]"
        self._emit("LLM", msg)

    def alert(self, rule: str, detail: str) -> None:
        """Kural motoru bir bildirim tetikledi (PROJECT_BRIEF S3.7)."""
        self._emit("ALERT", f"{rule} | {detail}")

    def warn(self, message: str) -> None:
        self._emit("WARN", message)

    def error(self, message: str) -> None:
        self._emit("ERROR", message)

    def debug(self, message: str) -> None:
        if settings.LOG_LEVEL.upper() == "DEBUG":
            self._to_file(f"[{self._ts()}] DEBUG  | {message}")

    def info(self, message: str) -> None:
        self._emit("INFO", message)


log = KervansarayLogger()


_NOISY = [
    "urllib3", "httpcore", "httpx", "requests",
    "groq", "groq._base_client", "openai",
    "werkzeug", "asyncio", "concurrent",
]


def setup_logging() -> None:
    """Python logging'i yapilandir: konsol WARNING+, dosya DEBUG, gurultuyu sustur."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    sh = logging.StreamHandler()
    sh.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    )
    sh.setLevel(logging.WARNING)
    root.addHandler(sh)

    for lib in _NOISY:
        logging.getLogger(lib).setLevel(logging.CRITICAL)

    if settings.LOG_TO_FILE:
        os.makedirs(os.path.dirname(settings.LOG_FILE) or ".", exist_ok=True)
        fh = RotatingFileHandler(
            settings.LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s"))
        fh.setLevel(logging.DEBUG)
        root.addHandler(fh)

    log.sys(f"Logging initialized (level={settings.LOG_LEVEL}, file={settings.LOG_FILE})")
