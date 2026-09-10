"""
fetchers/pdma_kp_fetcher.py
============================
Manual ingestion helper for PDMA KP advisories.

No public PDMA KP API currently exists. This script provides:
  1. A structured template for manually entering a new advisory.
  2. A function to append the advisory to data/raw_advisories.json.
  3. Validation that required fields are present.

Usage:
    python fetchers/pdma_kp_fetcher.py

The script prompts interactively. For automated bulk ingestion,
call ingest_advisory(advisory_dict) directly.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_ADVISORIES = ROOT / "data" / "raw_advisories.json"
RAW_ADVISORIES.parent.mkdir(parents=True, exist_ok=True)

REQUIRED_FIELDS = [
    "title", "body", "hazard_type", "severity", "issued_at",
    "source_org", "district", "language",
]

VALID_HAZARD_TYPES = ["flood", "flash_flood", "landslide", "glof", "other"]
VALID_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
VALID_LANGUAGES = ["en", "ur", "ru"]


def validate(advisory: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if not advisory.get(field):
            errors.append(f"Missing required field: {field}")

    ht = advisory.get("hazard_type", "")
    if ht and ht not in VALID_HAZARD_TYPES:
        errors.append(f"hazard_type must be one of {VALID_HAZARD_TYPES}, got '{ht}'")

    sev = advisory.get("severity", "").upper()
    if sev and sev not in VALID_SEVERITIES:
        errors.append(f"severity must be one of {VALID_SEVERITIES}, got '{sev}'")

    lang = advisory.get("language", "")
    if lang and lang not in VALID_LANGUAGES:
        errors.append(f"language must be one of {VALID_LANGUAGES}, got '{lang}'")

    return errors


def load_existing() -> list[dict]:
    if not RAW_ADVISORIES.exists():
        return []
    with open(RAW_ADVISORIES, encoding="utf-8") as f:
        return json.load(f)


def save_advisories(advisories: list[dict]) -> None:
    with open(RAW_ADVISORIES, "w", encoding="utf-8") as f:
        json.dump(advisories, f, ensure_ascii=False, indent=2)


def ingest_advisory(advisory: dict) -> bool:
    """Validate and append an advisory. Returns True on success."""
    advisory = dict(advisory)
    advisory["severity"] = advisory.get("severity", "").upper()

    # Auto-generate ID and ingestion timestamp
    if not advisory.get("alert_id"):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        advisory["alert_id"] = f"{advisory.get('source_org','SRC').replace(' ','_')}_{ts}"
    advisory["ingested_at"] = datetime.now(timezone.utc).isoformat()

    errors = validate(advisory)
    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"  - {e}")
        return False

    existing = load_existing()
    # Deduplicate by alert_id
    ids = {a["alert_id"] for a in existing}
    if advisory["alert_id"] in ids:
        print(f"Advisory {advisory['alert_id']} already exists — skipping.")
        return False

    existing.append(advisory)
    save_advisories(existing)
    print(f"Advisory ingested: {advisory['alert_id']}")
    return True


def interactive_ingest():
    print("\nPDMA KP / NDMA Manual Advisory Ingestor")
    print("─" * 40)
    print(f"Hazard types: {VALID_HAZARD_TYPES}")
    print(f"Severities:   {VALID_SEVERITIES}")
    print(f"Languages:    {VALID_LANGUAGES}")
    print()

    advisory = {
        "title": input("Title: ").strip(),
        "body": input("Body text (paste full advisory): ").strip(),
        "hazard_type": input("Hazard type [flood/flash_flood/landslide]: ").strip().lower(),
        "severity": input("Severity [LOW/MEDIUM/HIGH/EXTREME]: ").strip().upper(),
        "issued_at": input("Issued at (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS): ").strip(),
        "source_org": input("Source org [NDMA/PDMA KP/PMD]: ").strip(),
        "district": input("District [Chitral/Upper Chitral/All]: ").strip(),
        "language": input("Language [en/ur/ru]: ").strip().lower(),
    }

    success = ingest_advisory(advisory)
    if success:
        print(f"\nSaved to: {RAW_ADVISORIES}")
        print("Run the pipeline to rebuild knowledge.sqlite with updated content.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    interactive_ingest()
