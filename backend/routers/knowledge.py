"""
backend/routers/knowledge.py
=============================
Read-only endpoints for browsing the knowledge base (served from the
laptop-side SQLite built by the pipeline).

GET /knowledge/search      — keyword search over chunks
GET /knowledge/chunks      — paginated list of all chunks
GET /knowledge/meta        — package metadata

The backend mounts the same knowledge.sqlite produced by the pipeline,
making it the single source of truth for both the app and the API.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

# Path to offline package SQLite.
# Checked in this order:
#   1. root/offline_package/knowledge.sqlite  (pipeline output)
#   2. root/app/assets/offline_package/knowledge.sqlite  (Flutter asset copy)
# Override with KNOWLEDGE_DB env var for production.
import os as _os
_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = Path(_os.getenv(
    "KNOWLEDGE_DB",
    str(_ROOT / "offline_package" / "knowledge.sqlite"),
))
_FALLBACK_DB_PATH = _ROOT / "app" / "assets" / "offline_package" / "knowledge.sqlite"


def _get_conn() -> sqlite3.Connection:
    # Try pipeline output path first, then Flutter asset path
    db_path = _DB_PATH if _DB_PATH.exists() else _FALLBACK_DB_PATH
    if not db_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "knowledge.sqlite not found. "
                "Run: python pipeline/run_pipeline.py --skip-embed  "
                "OR set KNOWLEDGE_DB env var to the correct path."
            ),
        )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChunkResponse(BaseModel):
    chunk_id: str
    source_org: str
    doc_title: str
    pub_date: Optional[str]
    language: str
    page_num: Optional[int]
    chunk_text: str
    keywords: Optional[str]
    evidence_level: Optional[str]
    char_count: Optional[int]


class SearchResponse(BaseModel):
    query: str
    language: str
    total: int
    results: list[ChunkResponse]


class MetaResponse(BaseModel):
    meta: dict[str, str]


# ── Search ────────────────────────────────────────────────────────────────────
@router.get("/search", response_model=SearchResponse)
def search_knowledge(
    q: str = Query(..., min_length=2, description="Search query"),
    language: str = Query("en", description="en|ur|ru"),
    limit: int = Query(10, ge=1, le=50),
):
    conn = _get_conn()
    tokens = [t for t in q.lower().split() if len(t) >= 2]
    if not tokens:
        return SearchResponse(query=q, language=language, total=0, results=[])

    like_clauses = " OR ".join(
        "(chunk_text LIKE ? OR keywords LIKE ?)" for _ in tokens
    )
    args = [f"%{t}%" for t in tokens for _ in (0, 1)]
    score_expr = " + ".join(
        f"CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END" for _ in tokens
    )
    score_args = [f"%{t}%" for t in tokens]

    sql = f"""
        SELECT chunk_id, source_org, doc_title, pub_date, language,
               page_num, chunk_text, keywords, evidence_level, char_count,
               ({score_expr}) AS score
        FROM chunks
        WHERE language = ? AND ({like_clauses})
        ORDER BY score DESC
        LIMIT ?
    """
    params = score_args + [language] + args + [limit]
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = [
        ChunkResponse(
            chunk_id=r["chunk_id"],
            source_org=r["source_org"],
            doc_title=r["doc_title"],
            pub_date=r["pub_date"],
            language=r["language"],
            page_num=r["page_num"],
            chunk_text=r["chunk_text"],
            keywords=r["keywords"],
            evidence_level=r["evidence_level"],
            char_count=r["char_count"],
        )
        for r in rows
    ]
    return SearchResponse(query=q, language=language, total=len(results), results=results)


# ── List chunks ───────────────────────────────────────────────────────────────
@router.get("/chunks", response_model=list[ChunkResponse])
def list_chunks(
    language: str = Query("en"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM chunks WHERE language = ? ORDER BY source_org, chunk_index LIMIT ? OFFSET ?",
        (language, limit, offset),
    ).fetchall()
    conn.close()
    return [ChunkResponse(**dict(r)) for r in rows]


# ── Meta ──────────────────────────────────────────────────────────────────────
@router.get("/meta", response_model=MetaResponse)
def get_meta():
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM package_meta").fetchall()
    conn.close()
    return MetaResponse(meta={r["key"]: r["value"] for r in rows})
