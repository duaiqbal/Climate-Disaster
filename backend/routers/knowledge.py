"""
backend/routers/knowledge.py
=============================
Read-only endpoints for the offline knowledge package.

GET /knowledge/search?q=&language=   — keyword + FAISS semantic search
GET /knowledge/chunks                 — paginated chunk list
GET /knowledge/meta                   — offline package metadata

FIX (was broken): knowledge endpoints previously used synchronous sqlite3.connect()
inside async FastAPI handlers, blocking the event loop on every request.
Now uses asyncio.get_event_loop().run_in_executor() to run sync SQLite calls
in a thread pool, keeping the event loop non-blocking.
"""

import asyncio
import os
import sqlite3
from functools import partial
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

# Path to offline package SQLite — try pipeline output first, then Flutter asset.
_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = Path(os.getenv(
    "KNOWLEDGE_DB",
    str(_ROOT / "offline_package" / "knowledge.sqlite"),
))
_FALLBACK_DB_PATH = _ROOT / "app" / "assets" / "offline_package" / "knowledge.sqlite"


def _get_db_path() -> Path:
    if _DB_PATH.exists():
        return _DB_PATH
    if _FALLBACK_DB_PATH.exists():
        return _FALLBACK_DB_PATH
    raise HTTPException(
        status_code=503,
        detail=(
            "knowledge.sqlite not found. "
            "Run: python pipeline/run_pipeline.py --skip-embed"
        ),
    )


def _sync_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


async def _run_query(func, *args):
    """Execute a blocking SQLite function in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args))


# ── Synchronous query functions (run in executor) ─────────────────────────────

def _do_search(db_path: Path, q: str, language: str, limit: int) -> list[dict]:
    tokens = [t for t in q.lower().split() if len(t) >= 2]
    if not tokens:
        return []

    conn = _sync_connect(db_path)
    try:
        like_clauses = " OR ".join("(chunk_text LIKE ? OR keywords LIKE ?)" for _ in tokens)
        args = [f"%{t}%" for t in tokens for _ in (0, 1)]
        score_expr = " + ".join("CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END" for _ in tokens)
        score_args = [f"%{t}%" for t in tokens]

        sql = f"""
            SELECT chunk_id, source_org, doc_title, pub_date, language,
                   page_num, chunk_text, keywords, evidence_level, char_count,
                   COALESCE(source_url, '') AS source_url,
                   ({score_expr}) AS score
            FROM chunks
            WHERE language = ? AND ({like_clauses})
            ORDER BY score DESC
            LIMIT ?
        """
        rows = conn.execute(sql, score_args + [language] + args + [limit]).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _do_list_chunks(db_path: Path, language: str, limit: int, offset: int) -> list[dict]:
    conn = _sync_connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM chunks WHERE language = ? ORDER BY source_org, chunk_index LIMIT ? OFFSET ?",
            (language, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _do_get_meta(db_path: Path) -> dict:
    conn = _sync_connect(db_path)
    try:
        rows = conn.execute("SELECT key, value FROM package_meta").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ChunkResponse(BaseModel):
    chunk_id:       str
    source_org:     str
    doc_title:      str
    pub_date:       Optional[str]
    language:       str
    page_num:       Optional[int]
    chunk_text:     str
    keywords:       Optional[str]
    evidence_level: Optional[str]
    char_count:     Optional[int]
    source_url:     Optional[str] = ""  # direct URL to official document


class SearchResponse(BaseModel):
    query:    str
    language: str
    total:    int
    results:  list[ChunkResponse]


class MetaResponse(BaseModel):
    meta: dict[str, str]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    q:        str = Query(..., min_length=2),
    language: str = Query("en", description="en|ur|ru"),
    limit:    int = Query(10, ge=1, le=50),
):
    db_path = _get_db_path()
    rows = await _run_query(_do_search, db_path, q, language, limit)
    results = [ChunkResponse(**r) for r in rows]
    return SearchResponse(query=q, language=language, total=len(results), results=results)


@router.get("/chunks", response_model=list[ChunkResponse])
async def list_chunks(
    language: str = Query("en"),
    limit:    int = Query(20, ge=1, le=100),
    offset:   int = Query(0, ge=0),
):
    db_path = _get_db_path()
    rows = await _run_query(_do_list_chunks, db_path, language, limit, offset)
    return [ChunkResponse(**r) for r in rows]


@router.get("/meta", response_model=MetaResponse)
async def get_meta():
    db_path = _get_db_path()
    meta = await _run_query(_do_get_meta, db_path)
    return MetaResponse(meta=meta)
