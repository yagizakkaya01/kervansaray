"""search_notes (PROJECT_BRIEF S3.6, ROADMAP Faz 6).

Vardiya notları, prosedürler ve güvenlik raporlarında serbest metin araması.
Postgres yerel ILIKE ile çalışır; sıfır harici bağımlılık (Ponytail).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from .types import ToolResult, json_row

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


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
    """Not ve prosedürlerde anahtar kelime veya metin araması yapar."""
    clean_q = query.strip()
    limit_val = min(max(1, limit), MAX_LIMIT)

    clauses = ["(body ILIKE :term OR author ILIKE :term)"]
    params: dict[str, object] = {"term": f"%{_escape_ilike(clean_q)}%", "limit": limit_val}

    if author and author.strip():
        clauses.append("author ILIKE :author")
        params["author"] = f"%{_escape_ilike(author.strip())}%"

    where_sql = " AND ".join(clauses)
    sql = text(
        f"""
        SELECT id, ts, author, body
        FROM notes
        WHERE {where_sql}
        ORDER BY ts DESC
        LIMIT :limit
        """
    )
    rows = [json_row(r) for r in db.execute(sql, params).mappings().all()]
    return ToolResult(
        tool="search_notes",
        params={"query": clean_q, "author": author, "limit": limit_val},
        rows=rows,
        scalar=len(rows),
    )
