"""search_notes (PROJECT_BRIEF S3.6, ROADMAP Faz 6).

Vardiya notları, prosedürler ve güvenlik raporlarında serbest metin ve anahtar kelime araması.
Türkçe karakter ve kelime bazlı eşleştirme destekli (Ponytail: sıfır harici bağımlılık).
"""
from __future__ import annotations

import re
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from kervansaray.text.turkish import to_ascii
from .types import ToolResult, json_row

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# Arama kalitesini artırmak için Türkçe durak kelimeleri (stopwords)
STOPWORDS = {
    "ve", "veya", "ile", "icin", "için", "bir", "bu", "şu", "su", "o",
    "mi", "mu", "mı", "mü", "nedir", "nelerdir", "var", "yok", "olan",
    "göre", "gore", "nasil", "nasıl", "ne", "gibi", "kadar", "hakkında",
    "hakkinda", "ilgili", "geçerli", "gecerli", "durumda", "durumu",
    "konusu", "tarafından", "icin"
}


def _escape_ilike(val: str) -> str:
    """Postgres ILIKE özel karakterlerini (\\, %, _) kaçırır."""
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_notes(
    db: DbSession,
    *,
    query: str,
    author: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> ToolResult:
    """Not ve prosedürlerde serbest metin ve anahtar kelime araması yapar."""
    clean_q = query.strip()
    limit_val = min(max(1, limit), MAX_LIMIT)

    # 1. Tüm notları çek (author filtresi varsa uygula)
    sql_base = "SELECT id, ts, author, body FROM notes"
    params: dict[str, object] = {}
    if author and author.strip():
        sql_base += " WHERE author ILIKE :author"
        params["author"] = f"%{_escape_ilike(author.strip())}%"
    sql_base += " ORDER BY ts DESC"

    all_notes = [json_row(r) for r in db.execute(text(sql_base), params).mappings().all()]
    if not all_notes or not clean_q:
        return ToolResult(
            tool="search_notes",
            params={"query": clean_q, "author": author, "limit": limit_val},
            rows=[],
            scalar=0,
        )

    # 2. Akıllı Türkçe & Token Eşleme (Türkçe karakter ve kök toleranslı)
    q_ascii = to_ascii(clean_q)
    raw_words = re.findall(r"[a-zA-Z0-9çÇğĞıİöÖşŞüÜ]+", clean_q.lower())
    keywords = [to_ascii(w) for w in raw_words if len(w) >= 2 and to_ascii(w) not in STOPWORDS]

    scored_notes: list[tuple[float, dict]] = []
    for note in all_notes:
        body_text = note.get("body", "")
        author_text = note.get("author", "")
        combined_ascii = to_ascii(f"{author_text} {body_text}")

        score = 0.0

        # Tam öbek eşleşmesi
        if q_ascii in combined_ascii:
            score += 15.0

        # Anahtar kelime eşleşmeleri
        matched_kw_count = 0
        for kw in keywords:
            if kw in combined_ascii:
                matched_kw_count += 1
                if re.search(r"\b" + re.escape(kw), combined_ascii):
                    score += 3.0
                else:
                    score += 1.5

        if score > 0 or (keywords and matched_kw_count > 0):
            score += (matched_kw_count / max(len(keywords), 1)) * 5.0
            scored_notes.append((score, note))

    scored_notes.sort(key=lambda x: x[0], reverse=True)
    top_rows = [item[1] for item in scored_notes[:limit_val]]

    return ToolResult(
        tool="search_notes",
        params={"query": clean_q, "author": author, "limit": limit_val},
        rows=top_rows,
        scalar=len(top_rows),
    )

