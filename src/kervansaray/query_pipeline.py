"""Kervansaray Dogal Dil Sorgu Pipeline'i (PROJECT_BRIEF S3.2/S3.3).

Kullanici sorusunu alir -> Zaman ipuclarini cozer -> LLM'e gonderir (Function Calling)
-> Secilen tool'u SQL uzerinde calistirir -> Tablo ve narrative ile birlikte doner.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from time import monotonic, perf_counter
from typing import Any

from sqlalchemy.orm import Session as DbSession

from kervansaray.llm import gemini_client, get_available_clients
from kervansaray.llm.prompts import FEW_SHOT_EXAMPLES, build_system_prompt
from kervansaray.observability import LLM_LATENCY, LLM_REQUESTS
from kervansaray.text.dates import extract_time_hint
from kervansaray.text.turkish import to_ascii
from kervansaray.tools import GEMINI_FUNCTION_DECLARATIONS, OPENAI_TOOLS, dispatch_tool
from kervansaray.tools.types import ToolResult

log = logging.getLogger(__name__)

_DYNAMIC_WORDS = ("su an", "simdi", "bugun", "anlik", "canli", "doluluk")

# Kucuk model (Nemotron) bazen bu konulardaki sorulari yanlislikla '[DECLINED]'
# yapiyor. Soru bu ipuclarindan birini iceriyorsa ve ilk deneme tool cagirmadan
# dondu ise, sistem prompt'u pekistirilmis sekilde BIR kez daha denenir.
_DOMAIN_HINTS = (
    "plaka", "arac", "araç", "otopark", "giris", "giriş", "cikis", "çıkış",
    "gecis", "geçiş", "hareket", "sahada", "iceride", "içeride", "doluluk",
    "prosedur", "prosedür", "kara liste", "blacklist", "gece giris", "gece giriş",
    "overstay", "anomali", "supheli", "şüpheli", "ziyaret", "vardiya", "nizamiye",
    "bariyer", "kayitli", "kayıtlı", "kayitsiz", "kayıtsız", "misafir", "personel",
    "tescil", "kamera",
)


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
        plate_f = (args.get("plate") or "").strip()
        pk_f = (args.get("person_kind") or "").strip()
        scope = (
            f" {plate_f} plakalı araç için" if plate_f
            else f" '{pk_f}' türündeki araçlar için" if pk_f
            else ""
        )
        if metric == "unique_plates":
            return f"Belirtilen aralıkta{scope} toplam {cnt} farklı (tekil) araç tespit edildi."
        return f"Belirtilen aralıkta{scope} toplam {cnt} araç hareketi gerçekleşti."

    if tool_name == "query_events":
        cnt = len(result.rows)
        person_f = (args.get("person") or "").strip()
        pk_f = (args.get("person_kind") or "").strip()
        if cnt == 0:
            if person_f:
                return f"'{person_f}' için belirtilen dönemde araç geçiş kaydı bulunamadı."
            if pk_f:
                return f"Belirtilen dönemde '{pk_f}' türünde araç geçişi bulunamadı."
            return "Belirtilen kriterlere uyan araç geçiş kaydı bulunamadı."
        who = f" ({person_f})" if person_f else ""
        trunc = " (ilk 50 kayıt listeleniyor)" if result.truncated else ""
        return f"Kriterlere uygun {cnt} araç geçiş kaydı bulundu{who}{trunc}."

    if tool_name == "vehicle_history":
        plate = args.get("plate", "")
        cnt = len(result.rows)
        if cnt == 0:
            return f"{plate} plakasına ait sistemde herhangi bir geçiş kaydı bulunamadı."
        scalar_dict = result.scalar if isinstance(result.scalar, dict) else {}
        sessions = scalar_dict.get("sessions", [])
        is_inside = (
            bool(scalar_dict.get("is_inside"))
            if "is_inside" in scalar_dict
            else any(s.get("currently_inside") for s in sessions)
        )
        inside_str = "Araç şu anda otoparkta." if is_inside else "Araç şu anda dışarıda."

        label = scalar_dict.get("vehicle_label")
        owner = scalar_dict.get("owner_name")
        known = scalar_dict.get("known", False)
        is_bl = scalar_dict.get("is_blacklisted", False)

        if is_bl:
            ident_str = f"Araç KARA LİSTEDEDİR ({owner or label or 'Giriş Yasağı'})."
        elif owner and label:
            ident_str = f"Araç, {owner} ({label}) adına kayıtlıdır."
        elif owner:
            ident_str = f"Araç, {owner} adına kayıtlıdır."
        elif label:
            ident_str = f"Araç, '{label}' olarak kayıtlıdır."
        elif known:
            ident_str = "Araç sistemde kayıtlıdır."
        else:
            ident_str = (
                "Sistemde araç sahibi / tescil kaydı bulunmamaktadır "
                "(misafir/kayıtsız araç)."
            )

        return (
            f"{plate} plakalı araç: {ident_str} {inside_str} "
            f"(Sistemde {cnt} hareket kaydı mevcut)."
        )

    if tool_name == "find_anomalies":
        cnt = len(result.rows)
        rule = args.get("rule", "anomali")
        rule_tr = {
            "night_entry": "gece girişi (00:00-05:00)",
            "overstay": "48 saat üzeri kalma (overstay)",
            "blacklist": "kara liste ihlali",
            "unregistered_recurring": "kayıtsız sık ziyaret",
        }.get(rule, rule)
        if cnt == 0:
            return f"Belirtilen dönemde herhangi bir {rule_tr} anomalisi tespit edilmedi."
        plates = ", ".join(r.get("plate", "") for r in result.rows[:3])
        plates_str = f" (Plakalar: {plates})" if plates else ""
        return f"Sistemde {cnt} adet {rule_tr} anomalisi tespit edildi{plates_str}."

    if tool_name == "occupancy":
        cnt = result.scalar if result.scalar is not None else len(result.rows)
        as_of_val = args.get("as_of") or result.params.get("as_of")
        capacity = 100
        empty_spots = max(0, capacity - int(cnt))
        if as_of_val:
            return (
                f"Belirtilen an itibarıyla otoparkta {cnt} araç bulunuyordu "
                f"(Kapasite: {capacity}, Boş Yer: {empty_spots})."
            )
        return (
            f"Otoparkta şu anda {cnt} araç bulunuyor. "
            f"Toplam {capacity} araçlık tesiste {empty_spots} boş yer mevcuttur."
        )

    if tool_name == "search_notes":
        cnt = len(result.rows)
        q = args.get("query", "")
        if cnt == 0:
            return f"'{q}' konusuyla ilgili herhangi bir vardiya notu veya prosedür bulunamadı."
        first_note = result.rows[0]
        first_body = first_note.get("body", "").strip()
        author = first_note.get("author", "")
        author_str = f" ({author})" if author else ""
        if cnt == 1:
            return f"İlgili prosedür/not bulundu{author_str}: \"{first_body}\""
        return (
            f"'{q}' ile ilgili {cnt} adet kayıt bulundu. "
            f"İlgili talimat{author_str}: \"{first_body}\""
        )

    if tool_name == "registry_summary":
        sc = result.scalar if isinstance(result.scalar, dict) else {}
        total = sc.get("kayitli_arac", 0)
        active = sc.get("aktif_tescil", 0)
        bl = sc.get("kara_liste", 0)
        seen = sc.get("kapidan_gecmis", 0)
        pk = (args.get("person_kind") or "").strip()
        if pk:
            return (
                f"Sistemde '{pk}' türünde {total} kayıtlı araç var; "
                f"{active}'inin geçerli tescili aktif."
            )
        parts = ", ".join(f"{r['adet']} {r['tur']}" for r in result.rows[:4])
        dagilim = f" ({parts})" if parts else ""
        return (
            f"Sistemde kişiye bağlı {total} araç kayıtlı{dagilim}. Bunların "
            f"{active}'inin geçerli otopark tescili aktif, {bl}'si kara listede. "
            f"İncelenen dönemde bu araçlardan {seen}'i kapıdan geçti."
        )

    return f"{tool_name} başarıyla çalıştırıldı ({len(result.rows)} kayıt)."


def check_query_safety(query: str) -> tuple[bool, str]:
    """Sorgu metninde SQL enjeksiyonu veya zararlı komut kalıplarını denetler."""
    q_lower = query.lower()
    sql_patterns = [
        r"\b(drop|truncate|alter)\s+(table|database|schema|view)\b",
        r"\bdelete\s+from\b",
        r"\bupdate\s+\w+\s+set\b",
        r"\binsert\s+into\b",
        r"\bunion\s+(all\s+)?select\b",
        r"--\s*",
        r"/\*.*?\*/",
    ]
    for pattern in sql_patterns:
        if re.search(pattern, q_lower):
            return False, "SQL Manipülasyon Komutu Engellendi"

    injection_patterns = [
        r"\b(ignore|unut)\b.*\b(previous|onceki|talimat)\b",
        r"\b(system\s*prompt|sistem\s*talimat)\b",
        r"\bjailbreak\b",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, q_lower):
            return False, "Sistem Talimatı Müdahalesi Engellendi"

    return True, "Temiz (Doğrulandı)"


def build_audit_metadata(
    query: str,
    tool_name: str | None,
    tool_args: dict[str, Any] | None,
    time_hint: Any,
    status: str,
    safety_ok: bool,
    safety_msg: str,
) -> dict[str, Any]:
    """Model akıl yürütmesi ve güvenlik künyesini üretir."""
    if time_hint:
        if isinstance(time_hint, tuple) and len(time_hint) == 2:
            t_start, t_end = time_hint
            time_str = (
                f"{t_start.strftime('%d.%m.%Y %H:%M')} - "
                f"{t_end.strftime('%d.%m.%Y %H:%M')} (Pencere Çözümlendi)"
            )
        else:
            time_str = str(time_hint)
    else:
        clean_q = query.lower()
        if any(w in clean_q for w in ("su an", "şu an", "canli", "canlı", "anlik", "anlık")):
            time_str = "Canlı / Anlık Durum (Şu an)"
        else:
            time_str = "Tüm Tarihsel Dönem (Zaman Kısıtı Yok)"

    if tool_name == "search_notes":
        surface = "notes (Güvenlik Vardiya & Prosedür Notları)"
    elif tool_name == "registry_summary":
        surface = "vehicles + persons + registrations (Tescil Envanteri • Read-Only)"
    elif tool_name in ("vehicle_history", "aggregate_events", "find_anomalies", "occupancy"):
        surface = "v_events (Denormalize Olay View'ı • Read-Only)"
    else:
        surface = "SQL Çağrısı Yapılmadı (Doğrudan Çözümleme)"

    intent_map = {
        "vehicle_history": (
            "Plaka bazlı hareket geçmişi, oturumlar ve sürücü tescil künyesi sorgulandı."
        ),
        "aggregate_events": (
            "Belirtilen tarih ve filtre kriterlerine göre toplam araç hareketi "
            "istatistiği hesaplandı."
        ),
        "find_anomalies": (
            "48 saat üzeri sahada kalma (overstay) veya gece 03:00 anomalisi tarandı."
        ),
        "occupancy": "Tesis içindeki anlık araç sayısı ve doluluk durumu analiz edildi.",
        "search_notes": "Vardiya amirliği prosedürleri ve operasyonel nöbet defteri tarandı.",
        "registry_summary": "Kayıtlı araç envanteri ve tür dağılımı sorgulandı.",
    }
    justification = intent_map.get(
        tool_name,
        "Kapsam dışı veya genel soru: Veritabanı sorgusu tetiklenmeden nazik rehberlik sağlandı."
        if status == "declined"
        else "Doğrudan model yanıtı üretildi."
    )

    return {
        "safety_ok": safety_ok,
        "safety_label": safety_msg,
        "time_hint": time_str,
        "tool_name": tool_name or "Yok (Doğrudan)",
        "db_surface": surface,
        "justification": justification,
    }


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

    # 0. Güvenlik & Enjeksiyon Taraması (Pre-flight Guardrail)
    safety_ok, safety_msg = check_query_safety(clean_query)
    if not safety_ok:
        audit = build_audit_metadata(
            clean_query,
            tool_name=None,
            tool_args=None,
            time_hint=None,
            status="declined",
            safety_ok=False,
            safety_msg=safety_msg,
        )
        return {
            "query": user_text,
            "status": "declined",
            "provider": "kervansaray-guardrail",
            "tool_call": None,
            "tool_result": None,
            "narrative": (
                "Güvenlik Uyarısı: Girilen sorguda SQL manipülasyonu veya yetkisiz komut kalıbı "
                "tespit edildi. Kervansaray Doğal Dil Motoru yalnızca güvenli otopark istihbarat "
                "sorgularını işler."
            ),
            "audit": audit,
            "cached": False,
            "elapsed_seconds": round(perf_counter() - t0, 3),
        }

    # 1. Onbellek kontrolu
    cache_ref = as_of.isoformat() if as_of else "now"
    cache_key = f"{to_ascii(clean_query.lower())}:{cache_ref}"
    if use_cache:
        cached_entry = query_cache.get(cache_key)
        if cached_entry is not None:
            cached_entry["cached"] = True
            cached_entry["elapsed_seconds"] = round(perf_counter() - t0, 3)
            return cached_entry

    # 2. Calisma zamani ipuclari ve sistem talimati
    time_hint = extract_time_hint(clean_query, as_of=as_of)
    system_instruction = build_system_prompt(as_of=as_of, time_hint=time_hint)

    # 3. LLM cagir (aktif saglayicilar sirasiyla denenir; fallback destekli)
    if client:
        candidates = [client]
    else:
        candidates = get_available_clients()
        if not candidates:
            candidates = [gemini_client]

    def _invoke(
        sys_instr: str, tool_choice: str = "auto"
    ) -> tuple[dict[str, Any] | None, Any, Exception | None]:
        err: Exception | None = None
        for cand in candidates:
            prov = getattr(cand, "PROVIDER", "unknown")
            tools = OPENAI_TOOLS if prov == "nvidia" else GEMINI_FUNCTION_DECLARATIONS
            t_llm = perf_counter()
            try:
                gen_kwargs: dict[str, Any] = {
                    "system_instruction": sys_instr,
                    "tools": tools,
                    "few_shots": FEW_SHOT_EXAMPLES,
                }
                if prov == "nvidia":
                    gen_kwargs["tool_choice"] = tool_choice
                out = cand.generate(clean_query, **gen_kwargs)
                LLM_LATENCY.labels(prov).observe(perf_counter() - t_llm)
                LLM_REQUESTS.labels(prov, "ok").inc()
                return out, cand, None
            except Exception as exc:  # noqa: BLE001
                LLM_LATENCY.labels(prov).observe(perf_counter() - t_llm)
                LLM_REQUESTS.labels(prov, "error").inc()
                log.warning("LLM saglayicisi (%s) basarisiz, siradakine geciliyor: %s", prov, exc)
                err = exc
        return None, None, err

    _t_first = perf_counter()
    llm_out, used_client, last_error = _invoke(system_instruction)

    # Kapsam ici bir soruyu tool cagirmadan mi gecti? Bir kez daha, sertlestirilmis
    # talimat ve zorunlu tool_choice="required" ile dene (kucuk model hatasi telafisi).
    _clean_lower = to_ascii(clean_query.lower())
    if (
        llm_out is not None
        and not llm_out.get("function_call")
        and any(h in _clean_lower for h in _DOMAIN_HINTS)
    ):
        retry_instr = system_instruction + (
            "\n\nUYARI: Bu soru otopark/araç kapsamı İÇİNDEDİR. '[DECLINED]' deme; "
            "yukarıdaki araçlardan birini MUTLAKA çağır. Prosedür/not soruları "
            "search_notes, plaka soruları vehicle_history, kara liste/gece/overstay "
            "find_anomalies ile cevaplanır."
        )
        retry_out, retry_client, _ = _invoke(retry_instr, tool_choice="required")
        if retry_out is not None and retry_out.get("function_call"):
            llm_out, used_client = retry_out, retry_client

    if llm_out is None:
        log.exception("Tum LLM saglayicilari basarisiz oldu. Son hata: %s", last_error)
        fallback_prov = getattr(candidates[-1], "PROVIDER", "unknown") if candidates else "unknown"
        return {
            "query": user_text,
            "status": "error",
            "provider": fallback_prov,
            "tool_call": None,
            "tool_result": None,
            "narrative": (
                "Dil modeli sorguyu işlerken bir servis veya bağlantı hatası oluştu. "
                "Lütfen tekrar deneyin."
            ),
            "cached": False,
            "elapsed_seconds": round(perf_counter() - t0, 3),
        }

    prov_name = getattr(used_client, "PROVIDER", "unknown")
    provider = llm_out.get("provider", prov_name)

    # 4. Model direkt metin mi dondu (ornek: kapsam disi ret)?
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

        # Nazik ve rehberlik eden Türkçe mesaj (Sessiz Düzeltme & Yönlendirme)
        if status == "declined":
            narrative = (
                "Ben sadece Kervansaray otopark hareketlerini, araç tescillerini, vardiya "
                "prosedürlerini ve güvenlik anomalilerini analiz edebilen bir istihbarat "
                "motoruyum. Lütfen yukarıdaki hazır sorulardan birini seçin veya bir "
                "plaka/otopark durumu sorusu sorun."
            )
        else:
            narrative = resp_text or "Yanıt üretilemedi."

        audit = build_audit_metadata(
            clean_query,
            tool_name=None,
            tool_args=None,
            time_hint=time_hint,
            status=status,
            safety_ok=True,
            safety_msg="Temiz (Kapsam Denetlendi)",
        )

        out = {
            "query": user_text,
            "status": status,
            "provider": provider,
            "tool_call": None,
            "tool_result": None,
            "narrative": narrative,
            "audit": audit,
            "cached": False,
            "elapsed_seconds": round(perf_counter() - t0, 3),
        }
        if use_cache and status == "declined":
            query_cache.set(cache_key, out, is_dynamic=False)
        return out

    # 5. Tool calistir
    tool_name = fc.get("name", "")
    tool_args = fc.get("args", {})

    if tool_name == "find_anomalies":
        q_low = clean_query.lower()
        has_specific_day = any(
            w in q_low
            for w in (
                "dün", "dun", "bugün", "bugun", "nisan", "mayıs", "mayis",
                "haziran", "temmuz", "ağustos", "agustos", "eylül", "eylul",
                "ekim", "kasım", "kasim", "aralık", "aralik", "ocak", "şubat", "subat", "mart"
            )
        )
        if not has_specific_day:
            tool_args["start"] = "2026-01-01T00:00:00+03:00"

    tool_res = dispatch_tool(db, tool_name, tool_args, as_of=as_of)

    status = "error" if tool_res.note else "success"
    narrative = format_narrative(tool_name, tool_args, tool_res)

    audit = build_audit_metadata(
        clean_query,
        tool_name=tool_name,
        tool_args=tool_args,
        time_hint=time_hint,
        status=status,
        safety_ok=True,
        safety_msg="Temiz (Doğrulandı)",
    )

    result_payload = {
        "query": user_text,
        "status": status,
        "provider": provider,
        "tool_call": {"name": tool_name, "args": tool_args},
        "tool_result": tool_res.to_dict(),
        "narrative": narrative,
        "audit": audit,
        "cached": False,
        "elapsed_seconds": round(perf_counter() - t0, 3),
    }

    if use_cache and status == "success":
        is_dyn = is_dynamic_query(clean_query, tool_name)
        query_cache.set(cache_key, result_payload, is_dynamic=is_dyn)

    return result_payload
