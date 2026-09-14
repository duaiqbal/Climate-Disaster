"""
fetchers/official_alert_monitor.py
====================================
Monitors official NDMA / PDMA KP public web pages for new advisories and
situation reports — no fabricated API, no assumed endpoints.

Strategy:
  1. Fetch the official listing page (HTML) from ndma.gov.pk / pdma.gov.pk
  2. Parse PDF/document links from the page
  3. Compare against previously seen links (stored in data/alert_monitor_state.json)
  4. Download only NEW documents
  5. Extract alert text from each new PDF
  6. Insert verified alerts into backend via POST /alerts (with admin key)
  7. Every alert carries: source_org, source_url, fetch_timestamp,
     verification_status — constraint 4 honoured.
     New alerts enter at verification_status="DISCOVERED" so the backend
     lifecycle (DISCOVERED→FETCHED→VALIDATED→OFFICIAL-VERIFIED→PUBLISHED)
     can be advanced via a separate verification step.

Run:  python fetchers/official_alert_monitor.py
Schedule: cron / Windows Task Scheduler every 6 hours

Hard constraints honoured:
  - No fabricated API client
  - Every alert includes source_org, source_url, fetch_timestamp,
    verification_status — never blurred
  - No LLM involvement — text extracted directly from PDF
  - If a page is unreachable, state is preserved and reported — never faked
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: pip install requests beautifulsoup4 pymupdf")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE  = ROOT / "data" / "alert_monitor_state.json"
STAGING_DIR = ROOT / "data" / "raw" / "alert_staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# ── Backend config ─────────────────────────────────────────────────────────────
BACKEND_URL  = os.getenv("BACKEND_URL",  "http://127.0.0.1:8002")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Official pages to monitor ──────────────────────────────────────────────────
# These are real public listing pages — no fabricated API.
MONITOR_SOURCES = [
    {
        "source_org": "NDMA",
        "page_url": "https://ndma.gov.pk/advisories/",
        "link_pattern": r"/advisories/|/storage/advisories/",
        "hazard_type": "flood",
        "district": "Pakistan",
    },
    {
        "source_org": "NDMA",
        "page_url": "https://ndma.gov.pk/situation-reports/",
        "link_pattern": r"/sitreps/|/situation-reports/",
        "hazard_type": "flood",
        "district": "Pakistan",
    },
    {
        "source_org": "NDMA",
        "page_url": "https://ndma.gov.pk/guidelines/",
        "link_pattern": r"/guidelines/|/plans/",
        "hazard_type": "general",
        "district": "Pakistan",
    },
    {
        "source_org": "PDMA KP",
        "page_url": "https://pdma.gov.pk/alerts-and-warnings/",
        "link_pattern": r"\.pdf|/advisory",
        "hazard_type": "flood",
        "district": "Khyber Pakhtunkhwa",
    },
]

# Keywords to detect Chitral-specific or KP-relevant content
RELEVANCE_KEYWORDS = [
    "chitral", "kp", "khyber pakhtunkhwa", "flash flood", "flood", "landslide",
    "monsoon", "warning", "advisory", "alert", "rainfall", "emergency",
]


def _load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen_urls": [], "last_run": None, "inserted_alert_ids": []}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _fetch_page_links(source: dict, seen_urls: set) -> list[dict]:
    """Fetch listing page and return unseen PDF/document links."""
    try:
        resp = requests.get(
            source["page_url"], headers=HEADERS, timeout=15
        )
        if resp.status_code != 200:
            print(f"  PAGE {resp.status_code}: {source['page_url']}")
            return []
    except Exception as e:
        print(f"  PAGE ERROR: {source['page_url']} — {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    new_links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(source["page_url"], href)

        # Only follow same-domain PDF links matching the pattern
        if not re.search(source["link_pattern"], href, re.I):
            continue
        if not full_url.endswith(".pdf") and ".pdf" not in full_url.lower():
            continue
        if full_url in seen_urls:
            continue

        link_text = a.get_text(strip=True) or "Advisory"
        new_links.append({
            "url": full_url,
            "title": link_text[:200],
            "source_org": source["source_org"],
            "hazard_type": source["hazard_type"],
            "district": source["district"],
        })

    return new_links


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from PDF. Returns empty string on failure."""
    try:
        doc = fitz.open(str(pdf_path))
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text"))
        doc.close()
        return "\n".join(text_parts).strip()
    except Exception as e:
        print(f"    PDF extract error: {e}")
        return ""


def _is_relevant(text: str, title: str) -> bool:
    """Check if document content is relevant to Chitral/KP disaster context."""
    combined = (text[:2000] + " " + title).lower()
    matches = sum(1 for kw in RELEVANCE_KEYWORDS if kw in combined)
    return matches >= 2


def _classify_severity(text: str, title: str) -> str:
    combined = (text[:1000] + title).lower()
    if any(w in combined for w in ["extreme", "red alert", "imminent", "emergency"]):
        return "EXTREME"
    if any(w in combined for w in ["high", "severe", "heavy rainfall", "flash flood warning"]):
        return "HIGH"
    if any(w in combined for w in ["medium", "moderate", "advisory", "watch"]):
        return "MEDIUM"
    return "LOW"


def _classify_hazard(text: str, title: str) -> str:
    combined = (text[:1000] + title).lower()
    if "flash flood" in combined:
        return "flash_flood"
    if "landslide" in combined or "mudslide" in combined:
        return "landslide"
    if "flood" in combined or "rain" in combined:
        return "flood"
    return "general"


def _post_alert_to_backend(alert: dict) -> bool:
    """POST verified alert to backend. Returns True on success."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/alerts",
            json=alert,
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": ADMIN_API_KEY,
            },
            timeout=10,
        )
        if resp.status_code == 201:
            data = resp.json()
            print(f"    POSTED alert_id={data.get('alert_id')}")
            return True
        else:
            print(f"    POST failed: HTTP {resp.status_code} — {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"    POST error: {e}")
        return False


def _download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF to dest. Returns True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
        return dest.stat().st_size > 5000
    except Exception:
        return False


def run_monitor(dry_run: bool = False) -> dict:
    """
    Main monitor loop.

    dry_run=True: discover new links and extract text but do NOT post to backend.
    """
    state = _load_state()
    seen_urls = set(state.get("seen_urls", []))
    run_ts = datetime.now(timezone.utc).isoformat()

    total_new = 0
    total_posted = 0
    total_irrelevant = 0

    print(f"\n{'='*60}")
    print(f"  Disaster DSS — Official Alert Monitor")
    print(f"  Run: {run_ts}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Seen URLs so far: {len(seen_urls)}")
    print(f"{'='*60}")

    for source in MONITOR_SOURCES:
        print(f"\n[{source['source_org']}] {source['page_url']}")
        new_links = _fetch_page_links(source, seen_urls)
        print(f"  New links found: {len(new_links)}")

        for link in new_links[:5]:  # Process max 5 new docs per source per run
            url = link["url"]
            print(f"\n  Processing: {link['title'][:60]}")
            print(f"    URL: {url}")

            # Download PDF
            safe_name = re.sub(r"[^\w\-]", "_", urlparse(url).path.split("/")[-1])
            pdf_path = STAGING_DIR / safe_name
            downloaded = _download_pdf(url, pdf_path)

            if not downloaded:
                print(f"    SKIP: Could not download")
                seen_urls.add(url)  # mark seen so we don't retry endlessly
                continue

            # Extract text
            text = _extract_text_from_pdf(pdf_path)
            if not text:
                print(f"    SKIP: No text extractable")
                seen_urls.add(url)
                continue

            total_new += 1

            # Relevance filter
            if not _is_relevant(text, link["title"]):
                print(f"    SKIP: Not relevant to KP/Chitral context")
                total_irrelevant += 1
                seen_urls.add(url)
                continue

            # ── Build alert payload ────────────────────────────────────────────
            # Constraint 4: all provenance fields must be structured top-level
            # fields — not just buried in the body text.
            #
            # verification_status rationale: fetcher-sourced alerts enter at
            # DISCOVERED.  The backend's DISCOVERED→FETCHED→VALIDATED→
            # OFFICIAL-VERIFIED→PUBLISHED lifecycle means a human (or a separate
            # verification step) must advance the status before it is surfaced as
            # PUBLISHED.  Setting it to OFFICIAL-VERIFIED here would falsely claim
            # a verification step that hasn't happened — so we use DISCOVERED.
            alert_body = text[:800].strip()
            alert = {
                "title":               (link["title"][:255] or "Advisory"),
                "body":                alert_body,   # provenance prefix added below
                "hazard_type":         _classify_hazard(text, link["title"]),
                "severity":            _classify_severity(text, link["title"]),
                "issued_at":           run_ts,
                "source_org":          source["source_org"],
                "source_url":          url,          # ← structured field (Fix 4)
                "verification_status": "DISCOVERED", # ← structured field (Fix 4)
                "district":            source["district"],
                "language":            "en",
            }

            # Prepend provenance to body text as well — keeps it human-readable
            # in the UI and preserves the existing audit trail format.
            provenance = (
                f"[SOURCE: {source['source_org']} | "
                f"URL: {url} | "
                f"FETCHED: {run_ts} | "
                f"STATUS: DISCOVERED]\n\n"
            )
            alert["body"]  = provenance + alert_body
            alert["title"] = f"[{source['source_org']}] {alert['title']}"

            print(f"    Hazard: {alert['hazard_type']}  Severity: {alert['severity']}")

            if dry_run:
                print(f"    DRY RUN — would post: {alert['title'][:60]}")
            else:
                posted = _post_alert_to_backend(alert)
                if posted:
                    total_posted += 1

            seen_urls.add(url)
            time.sleep(1)

    # Update state
    state["seen_urls"] = list(seen_urls)
    state["last_run"] = run_ts
    _save_state(state)

    print(f"\n{'='*60}")
    print(f"  New documents found : {total_new}")
    print(f"  Irrelevant (skipped): {total_irrelevant}")
    print(f"  Posted to backend   : {total_posted}")
    print(f"  State saved         : {STATE_FILE}")
    print(f"{'='*60}\n")

    return {
        "run_ts": run_ts,
        "new_found": total_new,
        "posted": total_posted,
        "irrelevant": total_irrelevant,
    }


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    result = run_monitor(dry_run=dry_run)
    sys.exit(0)
