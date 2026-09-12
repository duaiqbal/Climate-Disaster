"""
backend/routers/rag.py
=======================
RAG query endpoint — grounded, provider-agnostic, hallucination-resistant.

POST /rag/query — ask a question, get a grounded answer with source attribution

Hard constraints honoured:
  Constraint 5: returns "insufficient evidence" when retrieval score is low
  Constraint 6: LLM provider is fully configurable via env var LLM_PROVIDER
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.knowledge import _get_db_path, _do_search, _run_query
from services.rag_service import RAGResponse, query_rag

router = APIRouter(prefix="/rag", tags=["RAG"])


class RAGQueryRequest(BaseModel):
    question: str
    language: str = "en"
    top_k: int = 5


class SourceRef(BaseModel):
    source_org: str
    doc_title: str
    pub_date: str
    evidence_level: str
    chunk_id: str


class RAGQueryResponse(BaseModel):
    question:         str
    answer:           str
    confidence:       str    # "sufficient" | "insufficient" | "no_llm"
    provider_used:    str
    generation_used:  bool
    retrieval_score:  int
    sources:          list[SourceRef]
    language:         str
    disclaimer: str = (
        "Answers are grounded in verified NDMA/PDMA/PMD documents. "
        "This is a decision-support tool — not an official emergency service. "
        "Always follow official NDMA/PDMA directives."
    )


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(payload: RAGQueryRequest):
    """
    Ask a disaster preparedness question.
    Returns a grounded answer sourced exclusively from verified official documents.
    Returns 'INSUFFICIENT EVIDENCE' if retrieval confidence is too low.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    # Retrieve from knowledge SQLite (thread-pool executor, non-blocking)
    db_path = _get_db_path()
    rows = await _run_query(
        _do_search, db_path, payload.question, payload.language, payload.top_k
    )

    # RAG service applies constraint 5 (refuse if low confidence) and
    # constraint 6 (provider dispatch via env var)
    result: RAGResponse = query_rag(
        question=payload.question,
        retrieved_chunks=rows,
    )

    return RAGQueryResponse(
        question=payload.question,
        answer=result.answer,
        confidence=result.confidence,
        provider_used=result.provider_used,
        generation_used=result.generation_used,
        retrieval_score=result.retrieval_score,
        sources=[SourceRef(**s) for s in result.sources],
        language=payload.language,
    )
