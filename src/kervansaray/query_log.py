"""Admin dashboard icin sorgu logu: /api/query'ye gelen her soru (metin + zaman).

Cevap veya IP tutulmaz - sadece "sorulan sorular" listesi. `MAX_ROWS` asilirsa
en eski kayitlar budanir (guestbook'taki MAX_ENTRIES deseniyle ayni fikir).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from kervansaray.db.models import QueryLog

MAX_ROWS = 2000


def record(db: Session, query_text: str) -> None:
    db.add(QueryLog(query_text=query_text[:500]))
    db.flush()

    subq = select(QueryLog.id).order_by(QueryLog.created_at.desc()).limit(MAX_ROWS)
    db.query(QueryLog).filter(QueryLog.id.notin_(subq)).delete(synchronize_session=False)


def list_recent(db: Session, limit: int = 200) -> list[QueryLog]:
    limit = max(1, min(limit, MAX_ROWS))
    stmt = select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))
