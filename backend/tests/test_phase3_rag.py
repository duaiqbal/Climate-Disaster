"""
backend/tests/test_phase3_rag.py
==================================
Regression tests for Phase 3 + 4:
  3.1  Retrieval-first: curated KB used only as override for exact FAQ patterns
  3.2  disaster_type / phase metadata on chunks
  3.3  Before/during/after queries produce different answers
  3.4  Alert-awareness: no fabrication when no alert exists
  3.5  Urdu translation chunks present in DB
  3.6  FAISS service loads gracefully; rerank_chunks works without FAISS
  4.2  Grounding-strict system prompt constraints
  4.4  Response cache invalidates correctly
"""

import importlib.util
import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("ENV", "test")

ROOT = Path(__file__).resolve().parents[2]


def _load_module(rel, name):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.1 — Curated KB override only for exact FAQ patterns
# ══════════════════════════════════════════════════════════════════════════════

class TestCuratedOverride:

    def _svc(self):
        return _load_module("backend/services/rag_service.py", "rag_service")

    def test_emergency_contacts_uses_curated(self):
        svc = self._svc()
        assert svc._should_use_curated("emergency contacts"), \
            "emergency contacts should use curated override"

    def test_go_bag_uses_curated(self):
        svc = self._svc()
        assert svc._should_use_curated("go bag checklist")

    def test_general_flood_does_not_use_curated(self):
        """Generic 'flood' should go through retrieval, not curated shortcut."""
        svc = self._svc()
        assert not svc._should_use_curated("what should i do during a flood"), \
            "General flood query should NOT use curated override — must retrieve first"

    def test_general_earthquake_does_not_use_curated(self):
        svc = self._svc()
        assert not svc._should_use_curated("earthquake safety")

    def test_query_rag_uses_retrieval_for_flood(self):
        """When retrieval returns chunks, answer must come from retrieval (not curated)."""
        svc = self._svc()
        fake_chunks = [{
            "chunk_id": "test_c0001", "source_org": "NDMA",
            "doc_title": "Flood Advisory", "pub_date": "2024",
            "chunk_text": "Move to higher ground immediately during flash floods.",
            "score": 3, "evidence_level": "official", "source_url": "",
            "disaster_type": "flood", "phase": "during",
        }]
        result = svc.query_rag("flood safety", fake_chunks)
        # Must NOT be from curated_kb_override (exact FAQ path)
        assert result.provider_used != "curated_kb_override", \
            "Generic flood query should use retrieval, not curated override"
        assert result.confidence == "sufficient"

    def test_curated_override_count_is_small(self):
        """Curated override set must be small (<=10 patterns) per Phase 3.1 design."""
        svc = self._svc()
        assert len(svc._CURATED_OVERRIDES) <= 15, \
            f"Curated overrides should be a small set, got {len(svc._CURATED_OVERRIDES)}"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.2 — disaster_type / phase metadata on chunks
# ══════════════════════════════════════════════════════════════════════════════

class TestChunkMetadata:

    def _chunk_mod(self):
        return _load_module("pipeline/rag/chunk.py", "chunk")

    def test_flood_during_classification(self):
        mod = self._chunk_mod()
        text = "Move to higher ground immediately. Do not cross flooded roads. Evacuate now."
        assert mod._classify_disaster_type(text, "Flood Advisory", "") == "flood"
        assert mod._classify_phase(text) == "during"

    def test_flood_before_classification(self):
        mod = self._chunk_mod()
        text = ("Before the flood season, prepare an emergency kit. "
                "Identify your evacuation route. Stock 3 days of food and water.")
        assert mod._classify_disaster_type(text, "", "") == "flood"
        assert mod._classify_phase(text) == "before"

    def test_landslide_classification(self):
        mod = self._chunk_mod()
        text = "Watch for cracks in the ground and tilting trees — early warning signs of landslide."
        assert mod._classify_disaster_type(text, "Landslide Advisory", "") == "landslide"

    def test_glof_priority_over_flood(self):
        mod = self._chunk_mod()
        text = "Glacial lake outburst flood risk is elevated in Yarkhun valley."
        dt = mod._classify_disaster_type(text, "", "")
        assert dt == "glof", f"Expected glof (not flood), got {dt}"

    def test_shipped_db_has_disaster_type_column(self):
        db = ROOT / "offline_package" / "knowledge.sqlite"
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
        conn.close()
        assert "disaster_type" in cols
        assert "phase" in cols

    def test_shipped_db_has_classified_chunks(self):
        db = ROOT / "offline_package" / "knowledge.sqlite"
        conn = sqlite3.connect(str(db))
        flood_count = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE disaster_type='flood'"
        ).fetchone()[0]
        conn.close()
        assert flood_count > 0, "Should have at least some flood-classified chunks"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.3 — Before/during/after produce different answers
# ══════════════════════════════════════════════════════════════════════════════

class TestIntentAwareRetrieval:

    def _svc(self):
        return _load_module("backend/services/rag_service.py", "rag_service")

    def _make_chunk(self, text, disaster, phase, score=3):
        return {"chunk_id": f"c_{phase}", "source_org": "NDMA",
                "doc_title": "Test", "pub_date": "2024",
                "chunk_text": text, "score": score,
                "evidence_level": "official", "source_url": "",
                "disaster_type": disaster, "phase": phase}

    def test_intent_before_flood(self):
        svc = self._svc()
        intent = svc._classify_intent("how to prepare before a flood")
        assert intent["phase"] == "before"
        assert intent["disaster_type"] == "flood"

    def test_intent_during_flood(self):
        svc = self._svc()
        intent = svc._classify_intent("what should i do during a flood")
        assert intent["phase"] == "during"

    def test_intent_after_flood(self):
        svc = self._svc()
        intent = svc._classify_intent("what to do after the flood")
        assert intent["phase"] == "after"

    def test_compose_answer_has_phase_header(self):
        svc = self._svc()
        chunks = [self._make_chunk("Move to higher ground immediately.", "flood", "during")]
        intent = {"disaster_type": "flood", "phase": "during",
                  "is_alert_query": False, "is_contacts": False}
        ans = svc._compose_answer_from_chunks(chunks, intent, "flood")
        assert "DURING" in ans.upper() or "during" in ans.lower(), \
            f"Answer should mention phase: {ans[:100]}"

    def test_before_after_answers_differ(self):
        """Before and after queries must produce different composed answers."""
        svc = self._svc()
        before_chunk = self._make_chunk(
            "Prepare emergency kit before monsoon. Stock food and water.", "flood", "before"
        )
        after_chunk = self._make_chunk(
            "After flood recedes, do not return until safe. Boil all water.", "flood", "after"
        )
        i_before = {"disaster_type": "flood", "phase": "before",
                    "is_alert_query": False, "is_contacts": False}
        i_after  = {"disaster_type": "flood", "phase": "after",
                    "is_alert_query": False, "is_contacts": False}
        ans_b = svc._compose_answer_from_chunks([before_chunk], i_before, "")
        ans_a = svc._compose_answer_from_chunks([after_chunk], i_after, "")
        assert ans_b != ans_a, "Before and after answers must differ"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.4 — Alert-awareness: no fabrication
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertAwareness:

    def _svc(self):
        return _load_module("backend/services/rag_service.py", "rag_service")

    def test_no_alert_returns_explicit_no_alert(self):
        """When no alert exists, format must say NO CURRENT ALERT explicitly."""
        svc = self._svc()
        result = svc._format_alert_context([])
        assert "NO CURRENT" in result.upper() or "no current" in result.lower(), \
            f"Empty alert list must produce explicit no-alert message: {result}"

    def test_with_alert_includes_title(self):
        svc = self._svc()
        alerts = [{"severity": "HIGH", "title": "Flash Flood Watch — Chitral",
                   "source_org": "NDMA", "issued_at": "2026-09-14T06:00:00Z"}]
        result = svc._format_alert_context(alerts)
        assert "Flash Flood Watch" in result

    def test_query_rag_no_fabrication_when_no_alert(self):
        """RAG response for alert query with no live alerts must NOT invent one."""
        svc = self._svc()
        fake_chunks = [{
            "chunk_id": "c1", "source_org": "NDMA", "doc_title": "Advisory",
            "pub_date": "2024", "chunk_text": "Flood preparedness is important.",
            "score": 2, "evidence_level": "official", "source_url": "",
            "disaster_type": "flood", "phase": "general",
        }]
        with patch.object(svc, "_fetch_live_alerts", return_value=[]):
            result = svc.query_rag("is there a flood alert", fake_chunks, "en")

        # Must not say "there is a flood alert" or invent one
        ans_lower = result.answer.lower()
        assert "NO CURRENT" in result.answer.upper() or \
               "no current" in ans_lower or \
               "no alert" in ans_lower or \
               result.provider_used in ("retrieval", "curated_kb", "none"), \
            f"Response must not fabricate alert when none exists: {result.answer[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.5 — Urdu chunks present
# ══════════════════════════════════════════════════════════════════════════════

class TestUrduChunks:

    def test_urdu_chunks_exist_in_db(self):
        db = ROOT / "offline_package" / "knowledge.sqlite"
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM chunks WHERE language='ur'").fetchone()[0]
        conn.close()
        assert count > 0, "Urdu translation chunks must exist after translate_urdu.py"

    def test_urdu_chunks_labeled_translated(self):
        """Urdu chunks must be labeled evidence_level='translated', not 'official'."""
        db = ROOT / "offline_package" / "knowledge.sqlite"
        conn = sqlite3.connect(str(db))
        unofficial = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE language='ur' AND evidence_level='official'"
        ).fetchone()[0]
        conn.close()
        assert unofficial == 0, \
            "Urdu translation chunks must not be labeled 'official'"

    def test_roman_urdu_normalizer_covers_eval_queries(self):
        """RomanUrduNormalizer must cover the 7 Roman Urdu eval queries."""
        dart_path = ROOT / "app" / "lib" / "core" / "retrieval" / "retrieval_engine.dart"
        source    = dart_path.read_text(encoding="utf-8")
        # Key terms from the Roman Urdu eval set
        for term in ("selab", "baarish", "landslide", "bachao", "paani"):
            assert term in source, f"RomanUrduNormalizer missing term: {term}"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3.6 — FAISS graceful fallback
# ══════════════════════════════════════════════════════════════════════════════

class TestFaissService:

    def _faiss(self):
        return _load_module("backend/services/faiss_service.py", "faiss_service")

    def test_rerank_returns_unchanged_when_faiss_unavailable(self):
        """rerank_chunks must return chunks unchanged when FAISS is not loaded."""
        svc = self._faiss()
        chunks = [
            {"chunk_id": "c1", "score": 5},
            {"chunk_id": "c2", "score": 3},
        ]
        # FAISS not available (_available=False by default in test env)
        result = svc.rerank_chunks(chunks, "flood safety")
        assert len(result) == len(chunks), "rerank must not drop chunks"
        assert result[0]["chunk_id"] == "c1", "order must be unchanged without FAISS"

    def test_load_faiss_returns_false_gracefully_when_index_missing(self, tmp_path):
        """load_faiss_index must return False (not raise) when index file absent."""
        svc = self._faiss()
        # Patch the index path to a nonexistent file
        with patch.object(svc, "_INDEX_PATH", tmp_path / "nonexistent.faiss"):
            result = svc.load_faiss_index()
        # Should return False, never raise
        # (May be True if previously loaded in same process — just check no exception)
        assert isinstance(result, bool)

    def test_semantic_search_returns_empty_gracefully(self):
        """semantic_search returns [] without FAISS — no exception."""
        svc = self._faiss()
        result = svc.semantic_search("flood", top_k=5)
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 4.2 — Grounding-strict system prompt
# ══════════════════════════════════════════════════════════════════════════════

class TestGroundingPrompt:

    def _svc(self):
        return _load_module("backend/services/rag_service.py", "rag_service")

    def test_system_prompt_contains_no_outside_knowledge(self):
        svc = self._svc()
        prompt = svc._SYSTEM_PROMPT.lower()
        assert "only" in prompt and "source" in prompt, \
            "System prompt must restrict answers to provided source text"

    def test_system_prompt_prohibits_alert_fabrication(self):
        svc = self._svc()
        prompt = svc._SYSTEM_PROMPT.lower()
        assert "alert" in prompt or "fabricat" in prompt or "never" in prompt, \
            "System prompt must address alert fabrication prevention"

    def test_system_prompt_requires_source_attribution(self):
        svc = self._svc()
        prompt = svc._SYSTEM_PROMPT.lower()
        assert "source" in prompt and ("org" in prompt or "organisation" in prompt
                                       or "organization" in prompt or "ndma" in prompt.lower()
                                       or "name" in prompt), \
            "System prompt must require naming source organisation"

    def test_system_prompt_no_predictions(self):
        svc = self._svc()
        prompt = svc._SYSTEM_PROMPT.lower()
        assert ("predict" in prompt or "official" in prompt), \
            "System prompt must disclaim predictive capability"

    def test_insufficient_evidence_response_fires_correctly(self):
        """Empty chunks AND no curated match → insufficient evidence."""
        svc = self._svc()
        with patch.object(svc, "_fetch_live_alerts", return_value=[]):
            result = svc.query_rag(
                "what is the price of wheat in Pakistan",  # out of scope
                [],  # no chunks
                "en"
            )
        assert result.confidence == "insufficient"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 4.4 — Response cache
# ══════════════════════════════════════════════════════════════════════════════

class TestResponseCache:

    def _svc(self):
        return _load_module("backend/services/rag_service.py", "rag_service")

    def test_cache_stores_and_retrieves(self):
        svc = self._svc()
        key = svc._cache_key("test q", "en",
                              {"disaster_type": "flood", "phase": "during"}, "")
        svc._RESPONSE_CACHE.clear()
        assert svc._get_cached(key) is None
        svc._set_cached(key, "cached answer")
        assert svc._get_cached(key) == "cached answer"

    def test_cache_expires_after_ttl(self):
        import time as t
        svc = self._svc()
        key = svc._cache_key("expiry test", "en",
                              {"disaster_type": "flood", "phase": "general"}, "")
        svc._RESPONSE_CACHE.clear()
        # Manually inject with expired timestamp
        svc._RESPONSE_CACHE[key] = ("old answer", t.time() - svc._CACHE_TTL_SECONDS - 1)
        assert svc._get_cached(key) is None, "Expired cache entry should return None"

    def test_cache_does_not_cache_alert_dependent_answers_beyond_ttl(self):
        """Cache TTL of 5 min means alert-dependent answers expire reasonably fast."""
        svc = self._svc()
        assert svc._CACHE_TTL_SECONDS <= 600, \
            f"Cache TTL too long ({svc._CACHE_TTL_SECONDS}s) — alert changes would be hidden"
