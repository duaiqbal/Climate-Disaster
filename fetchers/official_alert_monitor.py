"""
fetchers/official_alert_monitor.py
====================================
Multi-source monitor for all Pakistani disaster management authorities.

Architecture: one config entry per authority, one shared ingestion pipeline
(fetch → download → extract → classify → dedupe → POST) that runs identically
for every source.  Each source is independent — one failure does not abort others.

Verified integration status (checked 2026-09-14):
  INTEGRATED:
    NDMA         — ndma.gov.pk/advisories/, situation-reports/, guidelines/
    PDMA KP      — pdma.gov.pk/alerts-and-warnings/  (note: pdma.gov.pk = PDMA KP)
    PDMA Punjab  — pdma.punjab.gov.pk/weather-alerts/advisories/
    PMD FFD      — ffd.pmd.gov.pk/bulletins  (Flood Forecasting Division)

  NOT INTEGRATED (see docs/ARCHITECTURE.md for reasons):
    PDMA Sindh      — pdma.sindh.gov.pk has no stable public alerts listing page
    PDMA Balochistan— no verifiable official PDMA Balochistan domain found
    GB-DMA          — no dedicated GB-DMA website; GB alerts via NDMA national
    AJK-SDMA        — no public website; AJK alerts via NDMA national
    ICT             — covered by NDMA national alerts (no separate ICT-DMA site)
    PMD main site   — weather.gov.pk (new PMD domain) has JS-rendered content

State file: data/alert_monitor_state.json
  Shape: {
    "seen_urls": [...],
    "last_run": "ISO timestamp",
    "source_health": {
      "NDMA|https://...": {"last_ok": ..., "last_attempt": ..., "last_error": null, "count": N},
      ...
    }
  }
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: pip install requests beautifulsoup4 pymupdf")
    sys.exit(1)

ROOT        = Path(__file__).resolve().parents[1]
STATE_FILE  = ROOT / "data" / "alert_monitor_state.json"
STAGING_DIR = ROOT / "data" / "raw" / "alert_staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# ── Backend config ──────────────────────────────────────────────────────────────
BACKEND_URL   = os.getenv("BACKEND_URL",   "http://127.0.0.1:8002")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Source registry ─────────────────────────────────────────────────────────────
# Each entry defines exactly one scrapable listing page.
# province/region is used to populate alerts.province in the backend DB.
# max_per_run limits how many new PDFs to process per source per run.
MONITOR_SOURCES: list[dict] = [
    # ── NDMA (national — covers all of Pakistan including GB, AJK, ICT) ───────
    {
        "source_id":    "ndma_advisories",
        "source_org":   "NDMA",
        "province":     "Pakistan",
        "district":     "Pakistan",
        "page_url":     "https://ndma.gov.pk/advisories/",
        "link_pattern": r"/advisories/|/storage/advisories/",
        "hazard_type":  "flood",
        "max_per_run":  5,
    },
    {
        "source_id":    "ndma_sitreps",
        "source_org":   "NDMA",
        "province":     "Pakistan",
        "district":     "Pakistan",
        "page_url":     "https://ndma.gov.pk/situation-reports/",
        "link_pattern": r"/sitreps/|/situation-reports/",
        "hazard_type":  "flood",
        "max_per_run":  5,
    },
    {
        "source_id":    "ndma_guidelines",
        "source_org":   "NDMA",
        "province":     "Pakistan",
        "district":     "Pakistan",
        "page_url":     "https://ndma.gov.pk/guidelines/",
        "link_pattern": r"/guidelines/|/plans/",
        "hazard_type":  "general",
        "max_per_run":  3,
    },
    # ── PDMA KP ────────────────────────────────────────────────────────────────
    {
        "source_id":    "pdma_kp",
        "source_org":   "PDMA KP",
        "province":     "Khyber Pakhtunkhwa",
        "district":     "Khyber Pakhtunkhwa",
        "page_url":     "https://pdma.gov.pk/alerts-and-warnings/",
        "link_pattern": r"\.pdf|/advisory|/home/news/files/",
        "hazard_type":  "flood",
        "max_per_run":  5,
    },
    # ── PDMA Punjab ────────────────────────────────────────────────────────────
    # Confirmed reachable: pdma.punjab.gov.pk serves real PDF advisories under
    # /system/files/*.pdf  verified via search results 2026-09-14.
    {
        "source_id":    "pdma_punjab",
        "source_org":   "PDMA Punjab",
        "province":     "Punjab",
        "district":     "Punjab",
        "page_url":     "https://pdma.punjab.gov.pk/weather-alerts/advisories",
        "link_pattern": r"/system/files/.*\.pdf",
        "hazard_type":  "flood",
        "max_per_run":  5,
    },
    # ── PMD Flood Forecasting Division ─────────────────────────────────────────
    # ffd.pmd.gov.pk/bulletins serves real flood bulletins as downloadable PDFs.
    # Confirmed reachable: multiple bulletin PDFs verified via search 2026-09-14.
    {
        "source_id":    "pmd_ffd",
        "source_org":   "PMD",
        "province":     "Pakistan",
        "district":     "Pakistan",
        "page_url":     "https://ffd.pmd.gov.pk/bulletins",
        "link_pattern": r"/bulletin/\d+/download|/bulletins/archive/\d+/download",
        "hazard_type":  "flash_flood",
        "max_per_run":  5,
    },
]

# Broad relevance filter — accepts national + KP-specific documents
RELEVANCE_KEYWORDS = [
    "chitral", "kp", "khyber pakhtunkhwa", "flash flood", "flood", "landslide",
    "monsoon", "warning", "advisory", "alert", "rainfall", "emergency",
    "pakistan", "punjab", "sindh", "balochistan", "gilgit", "kashmir",
    "glof", "river", "evacuation", "preparedness",
]


# ── State management ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen_urls": [], "last_run": None, "source_health": {}}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _health_key(source: dict) -> str:
    return f"{source['source_id']}|{source['page_url']}"


def _update_health(
    state: dict,
    source: dict,
    *,
    success: bool,
    error: Optional[str] = None,
    new_alerts: int = 0,
) -> None:
    key = _health_key(source)
    now = datetime.now(timezone.utc).isoformat()
    existing = state["source_health"].get(key, {"count": 0})
    state["source_health"][key] = {
        "source_id":    source["source_id"],
        "source_org":   source["source_org"],
        "province":     source["province"],
        "page_url":     source["page_url"],
        "last_attempt": now,
        "last_ok":      now if success else existing.get("last_ok"),
        "last_error":   None if success else error,
        "alerts_contributed": existing.get("alerts_contributed", 0) + new_alerts,
        "count":        existing.get("count", 0) + 1,
    }


# ── Per-document helpers ────────────────────────────────────────────────────────

def _fetch_page_links(source: dict, seen_urls: set) -> list[dict]:
    """Fetch listing page and return unseen PDF links. Returns [] on any error."""
    try:
        resp = requests.get(source["page_url"], headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
    except Exception as e:
        raise RuntimeError(f"page fetch failed: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    new_links: list[dict] = []

    for a in soup.find_all("a", href=True):
        href   = a["href"]
        full   = urljoin(source["page_url"], href)
        if not re.search(source["link_pattern"], href, re.I):
            continue
        # Accept links that explicitly end in .pdf or contain /download in path
        path_lower = urlparse(full).path.lower()
        if not (path_lower.endswith(".pdf") or "/download" in path_lower):
            continue
        if full in seen_urls:
            continue
        text = a.get_text(strip=True) or "Advisory"
        new_links.append({
            "url":        full,
            "title":      text[:200],
            "source_org": source["source_org"],
            "hazard_type": source["hazard_type"],
            "district":   source["district"],
            "province":   source["province"],
        })

    return new_links


def _extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        doc = fitz.open(str(pdf_path))
        parts = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(parts).strip()
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}") from e


def _is_relevant(text: str, title: str) -> bool:
    combined = (text[:2000] + " " + title).lower()
    return sum(1 for kw in RELEVANCE_KEYWORDS if kw in combined) >= 2


def _classify_severity(text: str, title: str) -> str:
    c = (text[:1000] + title).lower()
    if any(w in c for w in ["extreme", "red alert", "imminent", "emergency"]):
        return "EXTREME"
    if any(w in c for w in ["high", "severe", "heavy rainfall", "flash flood warning"]):
        return "HIGH"
    if any(w in c for w in ["medium", "moderate", "advisory", "watch"]):
        return "MEDIUM"
    return "LOW"


def _classify_hazard(text: str, title: str) -> str:
    c = (text[:1000] + title).lower()
    if "flash flood" in c or "glof" in c:
        return "flash_flood"
    if "landslide" in c or "mudslide" in c:
        return "landslide"
    if "flood" in c or "rain" in c:
        return "flood"
    return "general"


def _download_pdf(url: str, dest: Path) -> None:
    """Download PDF to dest. Raises RuntimeError on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
        if dest.stat().st_size < 5000:
            raise ValueError("file too small — likely not a real PDF")
    except Exception as e:
        raise RuntimeError(f"PDF download failed: {e}") from e


def _post_alert(alert: dict) -> str:
    """POST alert to backend. Returns alert_id on success; raises on failure."""
    resp = requests.post(
        f"{BACKEND_URL}/alerts",
        json=alert,
        headers={"Content-Type": "application/json", "X-Admin-Key": ADMIN_API_KEY},
        timeout=10,
    )
    if resp.status_code == 201:
        return resp.json().get("alert_id", "?")
    raise RuntimeError(f"POST /alerts failed: HTTP {resp.status_code} — {resp.text[:120]}")


# ── Per-source ingestion (called independently for each source) ─────────────────

def _process_source(
    source: dict,
    seen_urls: set,
    state: dict,
    dry_run: bool,
    run_ts: str,
) -> dict:
    """
    Process one source.  Returns a result dict — never raises.
    Any exception is caught, logged to state['source_health'], and returned.
    """
    sid = source["source_id"]
    result = {
        "source_id": sid,
        "source_org": source["source_org"],
        "province": source["province"],
        "ok": False,
        "new_found": 0,
        "posted": 0,
        "skipped_irrelevant": 0,
        "error": None,
    }

    print(f"\n[{source['source_org']}] {source['page_url']}")

    # ── Step 1: Fetch listing page ──────────────────────────────────────────────
    try:
        new_links = _fetch_page_links(source, seen_urls)
    except RuntimeError as e:
        result["error"] = str(e)
        print(f"  FAIL: {e}")
        _update_health(state, source, success=False, error=str(e))
        return result

    print(f"  New links found: {len(new_links)}")

    # ── Step 2: Process each new document ──────────────────────────────────────
    for link in new_links[: source.get("max_per_run", 5)]:
        url = link["url"]
        print(f"\n  Processing: {link['title'][:60]}")
        print(f"    URL: {url}")

        safe = re.sub(r"[^\w\-]", "_", urlparse(url).path.split("/")[-1])
        pdf_path = STAGING_DIR / safe

        # Download
        try:
            _download_pdf(url, pdf_path)
        except RuntimeError as e:
            print(f"    SKIP (download): {e}")
            seen_urls.add(url)
            continue

        # Extract
        try:
            text = _extract_text_from_pdf(pdf_path)
        except RuntimeError as e:
            print(f"    SKIP (extract): {e}")
            seen_urls.add(url)
            continue

        result["new_found"] += 1

        # Relevance filter
        if not _is_relevant(text, link["title"]):
            print("    SKIP: not relevant")
            result["skipped_irrelevant"] += 1
            seen_urls.add(url)
            continue

        # Build structured alert payload (all provenance as top-level fields)
        alert_body = text[:800].strip()
        provenance = (
            f"[SOURCE: {source['source_org']} | URL: {url} | "
            f"FETCHED: {run_ts} | STATUS: DISCOVERED]\n\n"
        )
        alert = {
            "title":               f"[{source['source_org']}] {link['title'][:220]}",
            "body":                provenance + alert_body,
            "hazard_type":         _classify_hazard(text, link["title"]),
            "severity":            _classify_severity(text, link["title"]),
            "issued_at":           run_ts,
            "source_org":          source["source_org"],
            "source_url":          url,           # structured top-level field
            "verification_status": "DISCOVERED",  # structured top-level field
            "district":            source["district"],
            "province":            source["province"],  # ← province populated
            "language":            "en",
        }

        print(f"    hazard={alert['hazard_type']}  severity={alert['severity']}")

        if dry_run:
            print(f"    DRY RUN — would post")
        else:
            try:
                alert_id = _post_alert(alert)
                print(f"    POSTED alert_id={alert_id}")
                result["posted"] += 1
            except RuntimeError as e:
                print(f"    POST ERROR: {e}")

        seen_urls.add(url)
        time.sleep(1)

    result["ok"] = True
    _update_health(state, source, success=True, new_alerts=result["posted"])
    return result


# ── Main entry point ─────────────────────────────────────────────────────────────

def run_monitor(dry_run: bool = False) -> dict:
    """
    Run all sources independently.  Returns aggregate + per-source results.
    One source failing never aborts another.
    """
    state    = _load_state()
    seen_urls = set(state.get("seen_urls", []))
    run_ts   = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*65}")
    print(f"  ChitralSafe — Official Alert Monitor (multi-source)")
    print(f"  Run: {run_ts}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Sources: {len(MONITOR_SOURCES)}")
    print(f"  Seen URLs so far: {len(seen_urls)}")
    print(f"{'='*65}")

    source_results: list[dict] = []

    for source in MONITOR_SOURCES:
        res = _process_source(source, seen_urls, state, dry_run, run_ts)
        source_results.append(res)

    # Persist updated state
    state["seen_urls"] = list(seen_urls)
    state["last_run"]  = run_ts
    _save_state(state)

    # Aggregate totals
    total_new    = sum(r["new_found"] for r in source_results)
    total_posted = sum(r["posted"]    for r in source_results)
    total_failed = sum(1 for r in source_results if not r["ok"])
    total_irrel  = sum(r["skipped_irrelevant"] for r in source_results)

    print(f"\n{'='*65}")
    print(f"  PER-SOURCE SUMMARY:")
    for r in source_results:
        status = "OK" if r["ok"] else f"FAIL: {r['error']}"
        print(f"    [{r['source_org']:15s}] {status} | "
              f"found={r['new_found']} posted={r['posted']}")
    print(f"\n  TOTALS:")
    print(f"    New documents : {total_new}")
    print(f"    Irrelevant    : {total_irrel}")
    print(f"    Posted        : {total_posted}")
    print(f"    Source errors : {total_failed}/{len(MONITOR_SOURCES)}")
    print(f"{'='*65}\n")

    return {
        "run_ts":        run_ts,
        "new_found":     total_new,
        "posted":        total_posted,
        "irrelevant":    total_irrel,
        "source_errors": total_failed,
        "sources":       source_results,
    }


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    result  = run_monitor(dry_run=dry_run)
    sys.exit(0)
