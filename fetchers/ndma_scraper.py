"""
fetchers/ndma_scraper.py
=========================
Attempts to scrape the NDMA Pakistan website for new public advisories.

NOTE: No official public NDMA API exists as of 2026. This script
      scrapes the public web page as a best-effort measure. Manual
      verification of all ingested content is REQUIRED before
      inclusion in the offline package.

The scraper:
  1. Fetches the NDMA news/advisory listing page.
  2. Parses headline items and their dates.
  3. Filters for flood/landslide keywords.
  4. Saves raw HTML + parsed metadata to data/raw/scraped/.
  5. Does NOT auto-insert into the knowledge base — human review required.

Dependencies: requests, beautifulsoup4
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Install requests and beautifulsoup4:")
    print("  pip install requests beautifulsoup4")
    raise

ROOT = Path(__file__).resolve().parent.parent
SCRAPED_DIR = ROOT / "data" / "raw" / "scraped"
SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

NDMA_URL = "https://ndma.gov.pk/ndma-news/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

FLOOD_KEYWORDS = [
    "flood", "flash flood", "inundation", "river", "rainfall",
    "landslide", "mudslide", "GLOF", "monsoon", "Chitral",
    "سیلاب", "لینڈ سلائیڈ",
]


def is_disaster_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in FLOOD_KEYWORDS)


def scrape_ndma() -> list[dict]:
    print(f"Fetching: {NDMA_URL}")
    try:
        resp = requests.get(NDMA_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: Could not reach NDMA website: {e}")
        print("This is expected when offline. Using cached/manual data.")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []

    # Save raw HTML for audit trail
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_path = SCRAPED_DIR / f"ndma_raw_{ts}.html"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(resp.text)

    # Parse articles / news items — adjust selectors if NDMA redesigns
    for article in soup.select("article, .news-item, .post, h2, h3"):
        title_tag = article.find(["h2", "h3", "a"])
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title or not is_disaster_relevant(title):
            continue

        link = title_tag.get("href") or (title_tag.find("a") or {}).get("href", "")
        date_tag = article.find(class_=re.compile(r"date|time|publish"))
        date_str = date_tag.get_text(strip=True) if date_tag else "unknown"

        items.append({
            "title": title,
            "url": link,
            "date_raw": date_str,
            "source_org": "NDMA",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "requires_review": True,
        })

    # Save parsed results
    if items:
        out_path = SCRAPED_DIR / f"ndma_parsed_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"Found {len(items)} disaster-relevant items → {out_path}")
    else:
        print("No disaster-relevant items found on NDMA page.")

    return items


if __name__ == "__main__":
    results = scrape_ndma()
    print("\nIMPORTANT: All scraped content requires manual review")
    print("before ingestion into the offline knowledge base.")
    print("Use fetchers/pdma_kp_fetcher.py to ingest after review.")
