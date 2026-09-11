"""
backend/services/rag_service.py
================================
Provider-agnostic RAG + LLM service (hard constraints 5 and 6).

Constraint 5: If retrieval confidence is low (< MIN_CONFIDENCE_SCORE),
the service returns an "insufficient evidence" response and NEVER
fabricates an answer.

Constraint 6: The LLM provider is fully swappable via config.
No vendor SDK is scattered through business logic.
The provider is selected by LLM_PROVIDER env var:
  "none"     — no LLM; return retrieved text only (default, safe for offline)
  "openai"   — OpenAI Chat Completions API
  "ollama"   — local Ollama (free, runs on-device)
  "groq"     — Groq Cloud (fast, free tier available)

The core principle is preserved: generation only REPHRASES already-retrieved
verified content. It never adds facts, invents alerts, or overrides sources.

Environment variables:
  LLM_PROVIDER          — none | openai | ollama | groq  (default: none)
  LLM_MODEL             — model name (e.g. gpt-4o-mini, llama3, llama3-70b)
  LLM_API_KEY           — API key (openai / groq)
  LLM_BASE_URL          — base URL override (for ollama: http://localhost:11434/v1)
  LLM_MIN_CONFIDENCE    — min hit-score to attempt generation (default: 1)
  LLM_MAX_TOKENS        — max tokens for generation (default: 400)
"""

import os
from dataclasses import dataclass
from typing import Optional

# ── Config ─────────────────────────────────────────────────────────────────────

LLM_PROVIDER       = os.getenv("LLM_PROVIDER",       "none").lower()
LLM_MODEL          = os.getenv("LLM_MODEL",           "")
LLM_API_KEY        = os.getenv("LLM_API_KEY",         "")
LLM_BASE_URL       = os.getenv("LLM_BASE_URL",        "")
LLM_MIN_CONFIDENCE = int(os.getenv("LLM_MIN_CONFIDENCE", "1"))
LLM_MAX_TOKENS     = int(os.getenv("LLM_MAX_TOKENS",     "400"))

# ── System prompt — enforces grounding, prohibits fabrication ─────────────────

_SYSTEM_PROMPT = """You are a disaster safety assistant for communities in Chitral, KP, Pakistan.

RULES (non-negotiable):
1. You may ONLY use the provided SOURCE TEXT to answer. Never add facts not present in the source.
2. If the source text does not contain enough information to answer, reply exactly:
   "INSUFFICIENT EVIDENCE: The retrieved documents do not contain enough information to answer this question reliably."
3. Never invent hazard levels, alert statuses, locations, or official statements.
4. Never claim an answer is from NDMA/PDMA/PMD unless the source text explicitly states it.
5. Keep answers concise and in the same language as the question.
6. Always end with: "Source: <source_org>, <doc_title>, <pub_date>"

You are a grounding layer, not a creative assistant."""


@dataclass
class RAGResponse:
    answer: str
    sources: list[dict]          # list of {source_org, doc_title, pub_date, evidence_level}
    retrieval_score: int          # total hit count from retrieval
    confidence: str               # "sufficient" | "insufficient" | "no_llm"
    provider_used: str            # "none" | "openai" | "ollama" | "groq"
    generation_used: bool


# ── Provider implementations ──────────────────────────────────────────────────

def _call_openai(prompt: str, context: str) -> str:
    """Call OpenAI Chat Completions API."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL or None,
        )
        model = LLM_MODEL or "gpt-4o-mini"
        resp = client.chat.completions.create(
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.1,   # low temperature — factual, not creative
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except ImportError:
        return ""
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_ollama(prompt: str, context: str) -> str:
    """Call local Ollama via OpenAI-compatible endpoint."""
    try:
        from openai import OpenAI
        base = LLM_BASE_URL or "http://localhost:11434/v1"
        client = OpenAI(api_key="ollama", base_url=base)
        model = LLM_MODEL or "llama3"
        resp = client.chat.completions.create(
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except ImportError:
        return ""
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_groq(prompt: str, context: str) -> str:
    """Call Groq Cloud API (OpenAI-compatible)."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL or "https://api.groq.com/openai/v1",
        )
        model = LLM_MODEL or "llama3-70b-8192"
        resp = client.chat.completions.create(
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"SOURCE TEXT:\n{context}\n\nQUESTION: {prompt}"},
            ],
        )
        return resp.choices[0].message.content or ""
    except ImportError:
        return ""
    except Exception as e:
        return f"[LLM error: {e}]"


_PROVIDER_DISPATCH = {
    "openai": _call_openai,
    "ollama": _call_ollama,
    "groq":   _call_groq,
}


# ── Main service function ─────────────────────────────────────────────────────

def query_rag(
    question: str,
    retrieved_chunks: list[dict],
) -> RAGResponse:
    """
    Given a question and retrieved chunks, produce a grounded response.

    If LLM_PROVIDER == "none" or retrieval confidence is below
    LLM_MIN_CONFIDENCE, returns the raw retrieved text with no generation.

    Constraint 5: returns "INSUFFICIENT EVIDENCE" response when
    retrieval score < LLM_MIN_CONFIDENCE.

    Constraint 6: provider is fully configurable; no vendor SDK in
    business logic — dispatch table routes to provider implementations.
    """
    sources = [
        {
            "source_org":     c.get("source_org", ""),
            "doc_title":      c.get("doc_title", ""),
            "pub_date":       c.get("pub_date", ""),
            "evidence_level": c.get("evidence_level", "official"),
            "chunk_id":       c.get("chunk_id", ""),
        }
        for c in retrieved_chunks
    ]

    total_score = sum(c.get("score", 0) for c in retrieved_chunks)

    # ── Constraint 5: insufficient evidence check ─────────────────────────────
    if not retrieved_chunks or total_score < LLM_MIN_CONFIDENCE:
        return RAGResponse(
            answer=(
                "INSUFFICIENT EVIDENCE: The offline knowledge base does not contain "
                "enough verified information to answer this question reliably. "
                "Please consult official NDMA or PDMA KP sources directly."
            ),
            sources=[],
            retrieval_score=total_score,
            confidence="insufficient",
            provider_used="none",
            generation_used=False,
        )

    # Build context from retrieved chunks
    context_parts = []
    for c in retrieved_chunks[:3]:  # top 3 chunks for context window
        context_parts.append(
            f"[{c.get('source_org','')} — {c.get('doc_title','')} "
            f"({c.get('pub_date','')})]\n{c.get('chunk_text','')}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # ── No LLM: return raw retrieved text ────────────────────────────────────
    if LLM_PROVIDER == "none":
        raw_answer = "\n\n".join(c.get("chunk_text", "") for c in retrieved_chunks[:3])
        return RAGResponse(
            answer=raw_answer,
            sources=sources,
            retrieval_score=total_score,
            confidence="sufficient",
            provider_used="none",
            generation_used=False,
        )

    # ── LLM generation ────────────────────────────────────────────────────────
    caller = _PROVIDER_DISPATCH.get(LLM_PROVIDER)
    if not caller:
        # Unknown provider — safe fallback to raw text
        return RAGResponse(
            answer=context,
            sources=sources,
            retrieval_score=total_score,
            confidence="sufficient",
            provider_used=f"unknown:{LLM_PROVIDER}",
            generation_used=False,
        )

    generated = caller(question, context)

    # Post-generation safety: if the LLM output contains the
    # insufficient-evidence marker (from the system prompt), respect it.
    if "INSUFFICIENT EVIDENCE" in generated:
        return RAGResponse(
            answer=generated,
            sources=[],
            retrieval_score=total_score,
            confidence="insufficient",
            provider_used=LLM_PROVIDER,
            generation_used=True,
        )

    return RAGResponse(
        answer=generated,
        sources=sources,
        retrieval_score=total_score,
        confidence="sufficient",
        provider_used=LLM_PROVIDER,
        generation_used=True,
    )
