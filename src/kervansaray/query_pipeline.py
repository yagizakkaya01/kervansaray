"""Kervansaray Dogal Dil Sorgu Pipeline'i (PROJECT_BRIEF S3.2/S3.3).

Kullanici sorusunu alir -> Zaman ipuclarini cozer -> LLM'e gonderir (Function Calling)
-> Secilen tool'u SQL uzerinde calistirir -> Tablo ve narrative ile birlikte doner.
"""
from __future__ import annotations

import logging
from datetime import datetime
from time import monotonic, perf_counter
from typing import Any

from sqlalchemy.orm import Session as DbSession

from kervansaray.llm import gemini_client
from kervansaray.llm.prompts import FEW_SHOT_EXAMPLES, build_system_prompt
from kervansaray.observability import LLM_LATENCY, LLM_REQUESTS
from kervansaray.text.dates import extract_time_hint
from kervansaray.text.turkish import to_ascii
from kervansaray.tools import GEMINI_FUNCTION_DECLARATIONS, dispatch_tool
from kervansaray.tools.types import ToolResult

log = logging.getLogger(__name__)

_DYNAMIC_WORDS = ("su an", "simdi", "bugun", "anlik", "canli", "doluluk")


class QueryCache:
    """Bellek ici hibrit TTL sorgu onbellegi (PROJECT_BRIEF S12 / S4).

    - Gecmis tarihli veya kapsam disi sorgular: 24 saat (86400s) TTL
    - Canli/anlik sorgular ('su an', 'bugun', occupancy): 20s TTL
    - FIFO tahliye ile sabit bellek boyutu korur.
    """

    def __init__(
        self,
        max_size: int = 500,
        short_ttl: float = 20.0,
        long_ttl: float = 86400.0,
    ) -> None:
        self.max_size = max_size
        self.short_ttl = short_ttl
        self.long_ttl = long_ttl
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        if key not in self._cache:
            return None
        val, expires_at = self._cache[key]
        if monotonic() > expires_at:
            del self._cache[key]
            return None
        return dict(val)

    def set(self, key: str, val: dict[str, Any], *, is_dynamic: bool) -> None:
        ttl = self.short_ttl if is_dynamic else self.long_ttl
        if len(self._cache) >= self.max_size:
            del self._cache[next(iter(self._cache))]
        self._cache[key] = (dict(val), monotonic() + ttl)

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


query_cache = QueryCache()


def is_dynamic_query(text: str, tool_name: str | None = None) -> bool:
    """Sorgunun anlik/canli veri icerip icermedigini belirler."""
    if tool_name == "occupancy":
        return True
    clean = to_ascii(text.lower())
    return any(w in clean for w in _DYNAMIC_WORDS)


def format_narrative(tool_name: str, args: dict[str, Any], result: ToolResult) -> str:
    """SQL sonucunu operatore yonelik kisa, deterministik ve dogru bir ozete cevirir."""
    if result.note:
        return f"Sorgu çalıştırılamadı: {result.note}"

    if tool_name == "aggregate_events":
        metric = args.get("metric", "count")
        group_by = args.get("group_by")
        if group_by:
            total = sum(int(r.get("value", 0)) for r in result.rows)
            return (
                f"Belirtilen aralıkta '{group_by}' bazında {len(result.rows)} "
                f"grup listelendi (Toplam: {total})."
            )
        cnt = (
            result.scalar
            if result.scalar is not None
            else (result.rows[0].get("value", 0) if result.rows else 0)
        )
        if metric == "unique_plates":
            return f"Belirtilen aralıkta toplam {cnt} farklı (tekil) araç tespit edildi."
        return f"Belirtilen aralıkta toplam {cnt} araç hareketi gerçekleşti."

    if tool_name == "query_events":
        cnt = len(result.rows)
        trunc = " (ilk 50 kayıt listeleniyor)" if result.truncated else ""
        return f"Kriterlere uygun {cnt} araç geçiş kaydı bulundu{trunc}."

    if tool_name == "vehicle_history":
        plate = args.get("plate", "")
        cnt = len(result.rows)
        if cnt == 0:
            return f"{plate} plakasına ait sistemde herhangi bir geçiş kaydı bulunamadı."
        sessions = (
            result.scalar.get("sessions", [])
            if isinstance(result.scalar, dict)
            else []
        )
        is_inside = (
            bool(result.scalar.get("is_inside"))
            if isinstance(result.scalar, dict) and "is_inside" in result.scalar
            else any(s.get("currently_inside") for s in sessions)
        )
        inside_str = "Araç şu anda otoparkta." if is_inside else "Araç şu anda dışarıda."
        return f"{plate} plakalı araca ait {cnt} hareket kaydı bulundu. {inside_str}"

    if tool_name == "find_anomalies":
        cnt = len(result.rows)
        rule = args.get("rule", "anomali")
        if cnt == 0:
            return f"Belirtilen aralıkta herhangi bir '{rule}' anomalisi tespit edilmedi."
        return f"Belirtilen aralıkta {cnt} adet '{rule}' anomalisi tespit edildi."

    if tool_name == "occupancy":
        cnt = result.scalar if result.scalar is not None else len(result.rows)
        as_of_val = args.get("as_of") or result.params.get("as_of")
        if as_of_val:
            return f"Belirtilen an itibarıyla otoparkta {cnt} araç bulunuyordu."
        return f"Otoparkta şu anda {cnt} araç bulunuyor."

    if tool_name == "search_notes":
        cnt = len(result.rows)
        q = args.get("query", "")
        if cnt == 0:
            return f"'{q}' konusuyla ilgili herhangi bir vardiya notu veya prosedür bulunamadı."
        first_snippet = result.rows[0].get("body", "")[:120] if result.rows else ""
        return f"'{q}' ile ilgili {cnt} adet not bulundu: \"{first_snippet}\""

    return f"{tool_name} başarıyla çalıştırıldı ({len(result.rows)} kayıt)."


def run_query(
    user_text: str,
    db: DbSession,
    *,
    as_of: datetime | None = None,
    client: Any = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Dogal dil sorgusunu parse eder, tool cagirir ve sonuclari birlestirir.

    Donus:
        {
            "query": str,
            "status": "success" | "declined" | "error",
            "provider": str,
            "tool_call": {"name": ..., "args": ...} | None,
            "tool_result": dict | None,
            "narrative": str,
            "cached": bool,
            "elapsed_seconds": float,
        }
    """
    t0 = perf_counter()
    clean_query = user_text.strip()
    if not clean_query:
        return {
            "query": user_text,
            "status": "error",
            "provider": None,
            "tool_call": None,
            "tool_result": None,
            "narrative": "Sorgu metni boş olamaz.",
            "cached": False,
            "elapsed_seconds": 0.0,
        }

    # 0. Onbellek kontrolu
    cache_ref = as_of.isoformat() if as_of else "now"
    cache_key = f"{to_ascii(clean_query.lower())}:{cache_ref}"
    if use_cache:
        cached_entry = query_cache.get(cache_key)
        if cached_entry is not None:
            cached_entry["cached"] = True
            cached_entry["elapsed_seconds"] = round(perf_counter() - t0, 3)
            return cached_entry

    # 1. Calisma zamani ipuclari ve sistem talimati
    time_hint = extract_time_hint(clean_query, as_of=as_of)
    system_instruction = build_system_prompt(as_of=as_of, time_hint=time_hint)

    # 2. LLM cagir (varsayilan: gemini_client)
    llm = client or gemini_client
    prov_name = getattr(llm, "PROVIDER", "unknown")
    t_llm = perf_counter()
    try:
        llm_out = llm.generate(
            clean_query,
            system_instruction=system_instruction,
            tools=GEMINI_FUNCTION_DECLARATIONS,
            few_shots=FEW_SHOT_EXAMPLES,
        )
        LLM_LATENCY.labels(prov_name).observe(perf_counter() - t_llm)
        LLM_REQUESTS.labels(prov_name, "ok").inc()
    except Exception as exc:  # noqa: BLE001
        LLM_LATENCY.labels(prov_name).observe(perf_counter() - t_llm)
        LLM_REQUESTS.labels(prov_name, "error").inc()
        log.exception("LLM cagrisi sirasinda hata olustu: %s", exc)
        return {
            "query": user_text,
            "status": "error",
            "provider": prov_name,
            "tool_call": None,
            "tool_result": None,
            "narrative": (
                "Dil modeli sorguyu işlerken bir servis veya bağlantı hatası oluştu. "
                "Lütfen tekrar deneyin."
            ),
            "cached": False,
            "elapsed_seconds": round(perf_counter() - t0, 3),
        }

    provider = llm_out.get("provider", prov_name)

    # 3. Model direkt metin mi dondu (ornek: kapsam disi ret)?
    fc = llm_out.get("function_call")
    if not fc:
        resp_text = llm_out.get("response") or ""
        clean_resp = to_ascii(resp_text.lower())
        is_dec = (
            "[declined]" in clean_resp
            or "kapsam" in clean_resp
            or "ilgili degil" in clean_resp
        )
        status = "declined" if is_dec else "direct_response"
        out = {
            "query": user_text,
            "status": status,
            "provider": provider,
            "tool_call": None,
            "tool_result": None,
            "narrative": resp_text or "Yanıt üretilemedi.",
            "cached": False,
            "elapsed_seconds": round(perf_counter() - t0, 3),
        }
        if use_cache and status == "declined":
            query_cache.set(cache_key, out, is_dynamic=False)
        return out

    # 4. Tool calistir
    tool_name = fc.get("name", "")
    tool_args = fc.get("args", {})
    tool_res = dispatch_tool(db, tool_name, tool_args, as_of=as_of)

    status = "error" if tool_res.note else "success"
    narrative = format_narrative(tool_name, tool_args, tool_res)

    result_payload = {
        "query": user_text,
        "status": status,
        "provider": provider,
        "tool_call": {"name": tool_name, "args": tool_args},
        "tool_result": tool_res.to_dict(),
        "narrative": narrative,
        "cached": False,
        "elapsed_seconds": round(perf_counter() - t0, 3),
    }

    if use_cache and status == "success":
        is_dyn = is_dynamic_query(clean_query, tool_name)
        query_cache.set(cache_key, result_payload, is_dynamic=is_dyn)

    return result_payload
