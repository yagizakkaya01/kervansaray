# Tescilli Araç Envanteri Sayım Planı (Ponytail Yaklaşımı)

> **Sorun:** Kullanıcı *"tescilli araç envanterindeki araç sayısı"* veya *"sistemde kaç kayıtlı araç var"*
> sorduğunda model elinde tescil sayacı olmadığı için çaresiz kalıp `search_notes`'a sığınıyor ve
> alakasız vardiya notu döndürüyor.
> 
> **Kök Neden:** Kervansaray'da `v_events` (kapıdan geçenler: 38 tekil araç) ile `vehicles` (sisteme kayıtlı
> envanter: 205 araç) ayrışmış durumda. Mevcut 6 tool'un tamamı hareket odaklı; `vehicles` tablosunu
> sayan hiçbir tool yok.
> 
> Referans: `docs/TOOL_PARAMETER_EXPANSION_REVIEW.md`, `src/kervansaray/tools/events.py`.
> Tarih: 2026-09-10. Sahip: Gemini. İnceleme: Claude.

---

## 1. Mimari Karar: Yeni Tool YOK, `aggregate_events` Genişletmesi

Tool sayısı 6'da dondurulmuştur (Ponytail ilkesi). Ayrı bir `count_registry` tool'u eklemek yerine
sayım ve istatistiğin merkezi olan `aggregate_events` tool'u akıllandırılır:

* `metric`: `"count"` | `"unique_plates"` | **`"registered_vehicles"`**
* `start` ve `end` parametreleri: `metric="registered_vehicles"` durumunda **opsiyoneldir** (envanter zamandan bağımsız anlık durumdur).
* Filtre uyumu: `person_kind` parametresi (`guest` | `staff` | `vendor`) `vehicles` sayımında da çalışır.

---

## 2. Katman Katman Yapılacak Değişiklikler

### A. Tool Katmanı (`src/kervansaray/tools/events.py`)
```python
_METRICS = {"count", "unique_plates", "registered_vehicles"}

def aggregate_events(
    db: DbSession,
    *,
    metric: str,
    start: datetime | None = None,
    end: datetime | None = None,
    group_by: str | None = None,
    direction: str | None = None,
    registered: bool | None = None,
    plate: str | None = None,
    person_kind: str | None = None,
) -> ToolResult:
    _check(metric in _METRICS, f"metric {_METRICS} icinden olmali: {metric}")
    
    # registered_vehicles: doğrudan tescil tablosu (vehicles + persons)
    if metric == "registered_vehicles":
        where = []
        params = {}
        if person_kind == "unknown":
            where.append("v.person_id IS NULL")
        elif person_kind:
            _check(person_kind in {"guest", "staff", "vendor"}, f"gecersiz person_kind: {person_kind}")
            where.append("p.kind::text = :person_kind")
            params["person_kind"] = person_kind
        
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = text(
            f"SELECT count(*) AS v FROM vehicles v "
            f"LEFT JOIN persons p ON p.id = v.person_id {where_clause}"
        )
        val = int(db.execute(sql, params).scalar_one())
        return ToolResult(
            tool="aggregate_events",
            params=_clean_params(params | {"metric": metric}),
            scalar=val,
            rows=[{"metric": metric, "deger": val}],
        )
    
    # Geleneksel olay/hareket agregasyonu (v_events)
    _check(start is not None and end is not None, "Olay sayımı için start ve end zorunludur.")
    ...
```

### B. Tool Şeması (`src/kervansaray/tools/schemas.py`)
1. `aggregate_events` `metric` enum'ına `"registered_vehicles"` eklenir. Açıklama:
   `"'count': toplam geçiş adedi, 'unique_plates': kapıdan geçmiş tekil araç, 'registered_vehicles': sisteme kayıtlı tescilli araç envanter sayısı (tarihsiz)."`
2. `aggregate_events` `required` listesi `["metric"]` olarak güncellenir (veya prompt talimatıyla yönetilir).
3. **`search_notes` Negatif Kuralı:** Şema ve prompt açıklamasına açık engel:
   `"DİKKAT: Sayı, adet, istatistik veya araç/envanter sorularında ASLA bu aracı çağırma. Notlar yalnızca operasyonel prosedürler ve vardiya devir metinleri içindir."`

### C. Narrative Katmanı (`src/kervansaray/query_pipeline.py`)
`format_narrative` fonksiyonuna `registered_vehicles` dalı:
```python
if metric == "registered_vehicles":
    pk_str = f" ({args.get('person_kind')} türünde)" if args.get("person_kind") else ""
    return f"Sistemde tescilli/kayıtlı toplam {val} adet araç bulunmaktadır{pk_str}."
```

### D. Prompt & Few-Shot (`src/kervansaray/llm/prompts.py`)
Few-shot listesine 2 hedefli örnek:
1. `{"question": "Sistemde tescilli kaç araç var?", "tool_call": {"name": "aggregate_events", "args": {"metric": "registered_vehicles"}}}`
2. `{"question": "Kaç kayıtlı personel aracı bulunuyor?", "tool_call": {"name": "aggregate_events", "args": {"metric": "registered_vehicles", "person_kind": "staff"}}}`

---

## 3. Test ve Doğrulama Planı

- `tests/test_tools.py`:
  - `aggregate_events(metric="registered_vehicles")` → 205 döner.
  - `aggregate_events(metric="registered_vehicles", person_kind="staff")` → personel araç sayısını döner.
- Canlı sorgu testi:
  - `"tescilli araç envanterindeki araç sayısı"` → `aggregate_events(metric="registered_vehicles")` çağrılır, `search_notes`'a KAÇMAZ.
