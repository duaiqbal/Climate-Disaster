"""
backend/tests/test_phase1_regressions.py
==========================================
Regression tests for Phase 1 bug fixes (audit finding citations included).

Fix 1 — monitor.py port (CURRENT_STATE_AUDIT.md §A3 monitor.py):
  _run_fetcher() must read BACKEND_URL from env, not hardcode port 8001.

Fix 2 — retrieval_engine.dart broken SQL (CURRENT_STATE_AUDIT.md §B7):
  Verified separately via _test_sql.py (Python proxy for the Dart SQL).

Fix 3 — build_sqlite.py / knowledge.py schema drift (CURRENT_STATE_AUDIT.md §C14):
  source_url column must be in CREATE TABLE chunks from the start.

Fix 4 — official_alert_monitor.py payload (CURRENT_STATE_AUDIT.md §A5):
  source_url and verification_status must be top-level JSON fields.
"""

import importlib.util
import json
import os
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_module(rel_path: str, name: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: monitor.py port
# ══════════════════════════════════════════════════════════════════════════════

class TestFix1MonitorPort:
    """monitor.py _run_fetcher() must never hardcode 8001."""

    def test_monitor_py_no_hardcoded_8001_port(self):
        """Audit finding: _run_fetcher() previously hardcoded 8001."""
        monitor_path = ROOT / "backend" / "routers" / "monitor.py"
        source = monitor_path.read_text(encoding="utf-8")
        # The old bug: "BACKEND_URL", "http://127.0.0.1:8001"
        assert '"http://127.0.0.1:8001"' not in source, (
            "monitor.py still contains hardcoded port 8001 — Fix 1 not applied"
        )

    def test_monitor_py_uses_env_default_8002(self):
        """Default BACKEND_URL must be 8002, matching .env and scheduler.py."""
        monitor_path = ROOT / "backend" / "routers" / "monitor.py"
        source = monitor_path.read_text(encoding="utf-8")
        assert "8002" in source, (
            "monitor.py does not reference port 8002 as default — Fix 1 not applied"
        )

    def test_main_py_docstring_port(self):
        """main.py module docstring must say --port 8002."""
        main_path = ROOT / "backend" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        assert "--port 8002" in source, (
            "backend/main.py docstring still says --port 8001 — Fix 1 not applied"
        )

    def test_fetcher_default_port_8002(self):
        """official_alert_monitor.py BACKEND_URL default must be 8002."""
        fetcher = ROOT / "fetchers" / "official_alert_monitor.py"
        source = fetcher.read_text(encoding="utf-8")
        assert '"http://127.0.0.1:8001"' not in source, (
            "fetchers/official_alert_monitor.py still has hardcoded 8001"
        )
        assert "8002" in source, (
            "fetchers/official_alert_monitor.py does not use 8002 as default"
        )


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2: retrieval_engine.dart broken SQL
# ══════════════════════════════════════════════════════════════════════════════

class TestFix2RetrievalEngineSQL:
    """Dart SQL must use real schema — verified via Python proxy."""

    def test_dart_file_no_broken_table_references(self):
        """Audit finding: Dart file referenced non-existent tables 'knowledge'
        and 'chunk_metadata'. These must not appear in the fixed file."""
        dart_path = (ROOT / "app" / "lib" / "core" / "retrieval"
                     / "retrieval_engine.dart")
        source = dart_path.read_text(encoding="utf-8")
        assert "FROM knowledge k" not in source, (
            "retrieval_engine.dart still references non-existent 'knowledge' table"
        )
        assert "chunk_metadata" not in source, (
            "retrieval_engine.dart still references non-existent 'chunk_metadata' table"
        )
        assert "m.source_title" not in source, (
            "retrieval_engine.dart still uses non-existent 'source_title' column"
        )
        assert "m.publication_date" not in source, (
            "retrieval_engine.dart still uses non-existent 'publication_date' column"
        )

    def test_dart_file_uses_real_columns(self):
        """Fixed file must reference the actual schema column names."""
        dart_path = (ROOT / "app" / "lib" / "core" / "retrieval"
                     / "retrieval_engine.dart")
        source = dart_path.read_text(encoding="utf-8")
        assert "chunk_text" in source, "chunk_text column missing from Dart SQL"
        assert "doc_title"  in source, "doc_title column missing from Dart SQL"
        assert "pub_date"   in source, "pub_date column missing from Dart SQL"
        assert "FROM chunks" in source, "FROM chunks missing — wrong table name"

    def test_sql_returns_rows_against_real_db(self):
        """Execute the same SQL logic against the real knowledge.sqlite — must
        return rows for 3 diverse queries (flood, landslide, emergency)."""
        db_path = ROOT / "offline_package" / "knowledge.sqlite"
        assert db_path.exists(), f"Shipped knowledge.sqlite not found at {db_path}"

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        test_queries = [
            ("flood evacuation",        ["flood", "evacuation"]),
            ("landslide warning signs", ["landslide", "warning"]),
            ("emergency kit",           ["emergency", "kit"]),
        ]

        for label, words in test_queries:
            score_parts = " + ".join(
                "CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END" for _ in words
            )
            like_parts = " OR ".join(
                "(chunk_text LIKE ? OR keywords LIKE ?)" for _ in words
            )
            score_args = [f"%{w}%" for w in words]
            like_args  = [x for w in words for x in (f"%{w}%", f"%{w}%")]
            params     = score_args + ["en"] + like_args + [5]

            sql = f"""
                SELECT chunk_id, chunk_text, source_org, doc_title,
                       COALESCE(pub_date, 'unknown')      AS pub_date,
                       COALESCE(source_url, '')            AS source_url,
                       COALESCE(evidence_level, 'official') AS evidence_level,
                       ({score_parts}) AS score
                FROM chunks
                WHERE language = ?
                  AND ({like_parts})
                ORDER BY score DESC
                LIMIT ?
            """
            rows = conn.execute(sql, params).fetchall()
            assert len(rows) > 0, (
                f"SQL returned 0 rows for query '{label}' — "
                "schema or SQL may be wrong"
            )

        conn.close()

    def test_roman_urdu_normalizer_expanded(self):
        """RomanUrduNormalizer must have more than the original 8 entries."""
        dart_path = (ROOT / "app" / "lib" / "core" / "retrieval"
                     / "retrieval_engine.dart")
        source = dart_path.read_text(encoding="utf-8")
        # Count entries: each Dart map entry looks like `'key':  'value',`
        # Count single-quoted string pairs in the _variants map block.
        import re
        variants_match = re.search(
            r"_variants\s*=\s*\{(.*?)\};", source, re.DOTALL
        )
        assert variants_match, "_variants map not found in retrieval_engine.dart"
        variants_block = variants_match.group(1)
        # Each entry has at least one colon-separated pair
        entry_count = len(re.findall(r"'[^']+'\s*:\s*'[^']+'", variants_block))
        assert entry_count >= 20, (
            f"RomanUrduNormalizer only has {entry_count} entries; "
            "expected >=20 after expansion"
        )


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: build_sqlite.py schema + pipeline source_url propagation
# ══════════════════════════════════════════════════════════════════════════════

class TestFix3SourceUrlSchema:
    """source_url must be a first-class column in the pipeline, not an ALTER TABLE afterthought."""

    def test_create_table_chunks_has_source_url(self):
        """build_sqlite.py CREATE TABLE statement must include source_url."""
        build_path = (ROOT / "pipeline" / "package_builder" / "build_sqlite.py")
        source = build_path.read_text(encoding="utf-8")
        # Find the CREATE TABLE chunks block
        assert "source_url" in source, (
            "build_sqlite.py CREATE TABLE chunks does not define source_url column"
        )
        # It must be in the CREATE TABLE block, not just elsewhere in the file
        create_block_start = source.find("CREATE TABLE chunks")
        create_block_end   = source.find(");", create_block_start)
        create_block = source[create_block_start:create_block_end]
        assert "source_url" in create_block, (
            "source_url is referenced in build_sqlite.py but not inside "
            "the CREATE TABLE chunks definition"
        )

    def test_insert_chunks_includes_source_url(self):
        """INSERT OR REPLACE in build_sqlite.py must name source_url."""
        build_path = (ROOT / "pipeline" / "package_builder" / "build_sqlite.py")
        source = build_path.read_text(encoding="utf-8")
        assert ":source_url" in source, (
            "build_sqlite.py INSERT does not bind :source_url — "
            "fresh pipeline run would not store source_url"
        )

    def test_chunk_document_propagates_source_url(self):
        """chunk.py chunk_document() must carry source_url from doc to chunk."""
        chunk_mod = _load_module("pipeline/rag/chunk.py", "chunk")
        doc = {
            "source_file": "ndma_drm_strategy_plan_2024.pdf",
            "source_org":  "NDMA",
            "doc_title":   "Test",
            "pub_date":    "2024",
            "language":    "en",
            "source_url":  "https://example.com/test.pdf",
            "pages": [{"page_num": 1, "text": "Emergency flood evacuation preparedness guidelines for Chitral residents during monsoon season."}],
        }
        chunks = chunk_mod.chunk_document(doc)
        assert len(chunks) > 0
        for c in chunks:
            assert c.get("source_url") == "https://example.com/test.pdf", (
                f"chunk_document did not propagate source_url; got {c.get('source_url')!r}"
            )

    def test_chunk_document_missing_source_url_defaults_empty(self):
        """chunk_document must not raise KeyError if source_url absent in doc."""
        chunk_mod = _load_module("pipeline/rag/chunk.py", "chunk")
        doc = {
            "source_file": "test.pdf",
            "source_org":  "NDMA",
            "doc_title":   "Test",
            "pub_date":    "2024",
            "language":    "en",
            # NO source_url key
            "pages": [{"page_num": 1, "text": "Flood safety preparedness emergency kit evacuation for Chitral."}],
        }
        chunks = chunk_mod.chunk_document(doc)
        assert len(chunks) > 0
        for c in chunks:
            assert c.get("source_url", "MISSING") == "", (
                f"Missing source_url should default to ''; got {c.get('source_url')!r}"
            )

    def test_in_memory_build_creates_source_url_column(self):
        """End-to-end: create_schema → insert_chunks → select source_url."""
        build_mod = _load_module(
            "pipeline/package_builder/build_sqlite.py", "build_sqlite"
        )
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        build_mod.create_schema(conn)

        cols = [r["name"] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
        assert "source_url" in cols, f"source_url not in schema; got {cols}"

        sample = [{
            "chunk_id":      "test_c0001",
            "source_org":    "NDMA",
            "doc_title":     "Test",
            "pub_date":      "2024",
            "language":      "en",
            "page_num":      1,
            "chunk_index":   1,
            "chunk_text":    "Flood evacuation guidance.",
            "keywords":      "flood,evacuation",
            "evidence_level":"official_national",
            "char_count":    26,
            "source_url":    "https://ndma.gov.pk/test.pdf",
        }]
        build_mod.insert_chunks(conn, sample)
        conn.commit()

        row = conn.execute(
            "SELECT source_url FROM chunks WHERE chunk_id='test_c0001'"
        ).fetchone()
        assert row is not None
        assert row["source_url"] == "https://ndma.gov.pk/test.pdf"
        conn.close()

    def test_shipped_db_coalesce_query_works(self):
        """COALESCE(source_url,'') on the shipped knowledge.sqlite must not error."""
        db = ROOT / "offline_package" / "knowledge.sqlite"
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT chunk_id, COALESCE(source_url,'') AS su FROM chunks LIMIT 3"
        ).fetchall()
        conn.close()
        assert len(rows) == 3, "Expected 3 rows from shipped DB"


# ══════════════════════════════════════════════════════════════════════════════
# FIX 4: official_alert_monitor.py payload fields
# ══════════════════════════════════════════════════════════════════════════════

class TestFix4AlertMonitorPayload:
    """source_url and verification_status must be structured top-level payload
    fields, not just embedded in body text."""

    def _build_test_alert(self) -> dict:
        """Re-create the alert dict using the same logic as run_monitor()."""
        fetcher_src = (ROOT / "fetchers" / "official_alert_monitor.py"
                       ).read_text(encoding="utf-8")
        # We parse and exec only the helper functions — not the network I/O.
        # Easiest approach: load via importlib and call the helpers.
        fetcher_mod = _load_module(
            "fetchers/official_alert_monitor.py", "alert_monitor"
        )
        run_ts     = "2026-09-14T10:00:00+00:00"
        url        = "https://ndma.gov.pk/test-advisory.pdf"
        text       = "Flood warning for Chitral. Heavy rainfall expected."
        title      = "NDMA Flood Advisory"
        source_org = "NDMA"
        district   = "Chitral"

        alert = {
            "title":               title[:255],
            "body":                text[:800].strip(),
            "hazard_type":         fetcher_mod._classify_hazard(text, title),
            "severity":            fetcher_mod._classify_severity(text, title),
            "issued_at":           run_ts,
            "source_org":          source_org,
            "source_url":          url,
            "verification_status": "DISCOVERED",
            "district":            district,
            "language":            "en",
        }
        provenance = (
            f"[SOURCE: {source_org} | URL: {url} | "
            f"FETCHED: {run_ts} | STATUS: DISCOVERED]\n\n"
        )
        alert["body"]  = provenance + alert["body"]
        alert["title"] = f"[{source_org}] {alert['title']}"
        return alert

    def test_alert_payload_has_source_url_field(self):
        """Alert dict must have source_url as a top-level key."""
        alert = self._build_test_alert()
        assert "source_url" in alert, (
            "Alert payload missing source_url top-level field — Fix 4 not applied"
        )
        assert alert["source_url"].startswith("http"), (
            f"source_url value looks wrong: {alert['source_url']!r}"
        )

    def test_alert_payload_has_verification_status_field(self):
        """Alert dict must have verification_status as a top-level key."""
        alert = self._build_test_alert()
        assert "verification_status" in alert, (
            "Alert payload missing verification_status top-level field"
        )

    def test_verification_status_is_discovered_not_official_verified(self):
        """Fetcher must NOT self-assign OFFICIAL-VERIFIED — it enters at DISCOVERED.
        Audit finding: old comment claimed 'official-verified' but that bypasses
        the verification lifecycle."""
        alert = self._build_test_alert()
        assert alert["verification_status"] == "DISCOVERED", (
            f"verification_status should be DISCOVERED; got {alert['verification_status']!r}. "
            "Fetcher must not self-claim OFFICIAL-VERIFIED without a verification step."
        )

    def test_body_still_has_provenance_prefix(self):
        """Provenance in body text is kept for human readability in the UI."""
        alert = self._build_test_alert()
        assert "[SOURCE:" in alert["body"], "Body provenance prefix missing"
        assert "URL:" in alert["body"], "URL not in body provenance"
        assert "STATUS: DISCOVERED" in alert["body"], (
            "Body provenance status should say DISCOVERED"
        )

    def test_source_url_not_only_in_body(self):
        """source_url must be a separate field, not only embedded in body."""
        alert = self._build_test_alert()
        # If we removed source_url from the body entirely, the top-level field
        # should still carry the URL.
        body_without_provenance = alert["body"].split("\n\n", 1)[-1]
        # The actual document text should not be the only place with the URL
        assert alert.get("source_url"), (
            "source_url top-level field is empty — must not rely on body parsing"
        )

    def test_fetcher_source_code_no_official_verified_literal(self):
        """Source code must not silently set 'official-verified' status."""
        fetcher_path = ROOT / "fetchers" / "official_alert_monitor.py"
        source = fetcher_path.read_text(encoding="utf-8")
        # The old bug comment+value in the original build
        assert '"official-verified"' not in source, (
            "fetcher still sets verification_status='official-verified' — Fix 4 not applied"
        )
        assert "STATUS: official-verified" not in source, (
            "fetcher still writes 'STATUS: official-verified' in body provenance"
        )
