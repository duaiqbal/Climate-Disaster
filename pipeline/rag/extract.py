"""
pipeline/rag/extract.py
=======================
Step 1 of the RAG pipeline: extract raw text from official PDF advisories.

Input:  data/raw/*.pdf
Output: data/extracted/*.json  (one JSON file per source document)

Each output JSON has the shape:
{
    "source_file": "ndma_flood_advisory_2023.pdf",
    "source_org":  "NDMA",
    "doc_title":   "National Flood Advisory 2023",
    "pub_date":    "2023-07-15",
    "language":    "en",
    "pages": [
        {"page_num": 1, "text": "..."},
        ...
    ]
}

Dependencies: pymupdf (import fitz)
"""

import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Source metadata registry ───────────────────────────────────────────────────
# Maps filename stem patterns to metadata — update when new PDFs are added.
SOURCE_REGISTRY = [
    {
        "pattern": r"ndma.*flood",
        "source_org": "NDMA",
        "language": "en",
        "doc_title": "NDMA Flood Advisory",
    },
    {
        "pattern": r"ndma.*landslide",
        "source_org": "NDMA",
        "language": "en",
        "doc_title": "NDMA Landslide Advisory",
    },
    {
        "pattern": r"pdma.*kp.*flood",
        "source_org": "PDMA KP",
        "language": "en",
        "doc_title": "PDMA KP Flood Guidelines",
    },
    {
        "pattern": r"pdma.*kp.*land",
        "source_org": "PDMA KP",
        "language": "en",
        "doc_title": "PDMA KP Landslide Guidelines",
    },
    {
        "pattern": r"pmd",
        "source_org": "PMD",
        "language": "en",
        "doc_title": "PMD Weather Advisory",
    },
    {
        "pattern": r"urdu|اردو",
        "source_org": "NDMA",
        "language": "ur",
        "doc_title": "NDMA Advisory (Urdu)",
    },
]

DEFAULT_META = {
    "source_org": "NDMA",
    "language": "en",
    "doc_title": "Official Disaster Advisory",
}


def _resolve_meta(filename: str) -> dict:
    lower = filename.lower()
    for entry in SOURCE_REGISTRY:
        if re.search(entry["pattern"], lower):
            return entry
    return DEFAULT_META


def _extract_pub_date(text: str) -> str:
    """Try to pull a date from the first 500 chars of extracted text."""
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{4})\b",
        r"\b((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{4})\b",
    ]
    snippet = text[:500]
    for pat in patterns:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            return m.group(1)
    return "unknown"


def extract_pdf(pdf_path: Path) -> dict:
    meta = _resolve_meta(pdf_path.name)
    doc = fitz.open(str(pdf_path))

    pages = []
    full_text_head = ""
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append({"page_num": page_num, "text": text})
            if page_num == 1:
                full_text_head = text

    doc.close()

    pub_date = _extract_pub_date(full_text_head)

    return {
        "source_file": pdf_path.name,
        "source_org": meta["source_org"],
        "doc_title": meta["doc_title"],
        "pub_date": pub_date,
        "language": meta["language"],
        "pages": pages,
    }


def main():
    pdf_files = sorted(RAW_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {RAW_DIR}")
        print("Place official NDMA/PDMA KP/PMD PDFs there and re-run.")
        # For demo purposes, create a synthetic source file
        _create_demo_source()
        pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    for pdf_path in pdf_files:
        print(f"Extracting: {pdf_path.name}")
        try:
            result = extract_pdf(pdf_path)
            out_path = OUT_DIR / (pdf_path.stem + ".json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            page_count = len(result["pages"])
            print(f"  → {out_path.name} ({page_count} pages, lang={result['language']})")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nExtraction complete. Output in: {OUT_DIR}")


def _create_demo_source():
    """Creates a synthetic PDF for demo/testing when no real PDFs are present."""
    try:
        doc = fitz.open()
        content_pages = [
            (
                "NDMA Flood Advisory – Chitral, KP\nDate: 2024-07-15\n\n"
                "IMMEDIATE ACTIONS DURING FLOOD:\n"
                "1. Move immediately to higher ground. Do not wait for official orders.\n"
                "2. Avoid walking or driving through floodwater — 15 cm of fast water can knock you down.\n"
                "3. If trapped, move to the highest point and signal for help.\n"
                "4. Turn off electricity at the main breaker before evacuating.\n"
                "5. Do not return until authorities confirm it is safe.\n\n"
                "BEFORE FLOOD SEASON:\n"
                "- Prepare a go-bag with water, food, documents, torch, and first aid.\n"
                "- Know your evacuation route to the nearest relief camp.\n"
                "- Register with your local PDMA office if you live in a high-risk zone.\n"
                "Source: National Disaster Management Authority (NDMA), Pakistan."
            ),
            (
                "NDMA Flash Flood Warning Procedures\n\n"
                "Flash floods can develop in minutes. Warning signs:\n"
                "- Sudden rise in river or stream level\n"
                "- Roaring sound from upstream\n"
                "- Debris and mud in water flow\n\n"
                "IMMEDIATE RESPONSE:\n"
                "If you see any of these signs, move to high ground IMMEDIATELY.\n"
                "Do not attempt to cross flooded roads or bridges.\n"
                "Call emergency services: PDMA KP Helpline 1700\n\n"
                "POST-FLOOD SAFETY:\n"
                "- Avoid floodwater — it may be electrically charged or contaminated.\n"
                "- Document damage for insurance/relief claims.\n"
                "- Boil all drinking water for at least 1 minute.\n"
                "Source: NDMA Pakistan, PMD Early Warning System."
            ),
            (
                "PDMA KP Landslide Advisory – Chitral District\n\nDate: 2024-06-10\n\n"
                "LANDSLIDE WARNING SIGNS:\n"
                "- New cracks appearing in soil, roads, or building walls\n"
                "- Tilting or leaning of trees, utility poles, or fences\n"
                "- Unusual bulging of ground surface\n"
                "- Springs, seeps, or saturated ground where not previously present\n"
                "- Sounds of cracking wood or rocks\n\n"
                "DURING A LANDSLIDE:\n"
                "- Move away from the path of the landslide as quickly as possible.\n"
                "- If escape is impossible, curl into a ball and protect your head.\n"
                "- Stay away from the slide area — secondary slides are common.\n\n"
                "AFTER A LANDSLIDE:\n"
                "- Stay out of the slide area.\n"
                "- Check for injured or trapped persons without entering the slide area.\n"
                "- Report slide to PDMA KP: 1700\n"
                "Source: Provincial Disaster Management Authority KP."
            ),
            (
                "PMD Seasonal Weather Outlook – Northern Pakistan\nDate: 2024-05-01\n\n"
                "The monsoon season (July–September) is expected to bring above-normal "
                "rainfall in Chitral, Dir, and Swat districts based on La Nina conditions.\n\n"
                "KEY RISKS:\n"
                "- Flash floods in narrow valleys and along the Chitral River\n"
                "- Increased landslide probability on slopes above 15 degrees\n"
                "- GLOF risk from glacial lake outbursts (Chitral, Gilgit)\n\n"
                "PREPAREDNESS RECOMMENDATIONS:\n"
                "- Communities in flood plains should prepare evacuation plans before July.\n"
                "- Local administrations should pre-position emergency supplies.\n"
                "- Households should store 72-hour emergency food and water supply.\n\n"
                "Source: Pakistan Meteorological Department (PMD)."
            ),
            (
                "سیلاب سے بچاؤ کے اقدامات – این ڈی ایم اے\nتاریخ: ۲۰۲۴-۰۷-۱۵\n\n"
                "فوری اقدامات:\n"
                "۱. فوری طور پر اونچی جگہ پر جائیں۔\n"
                "۲. سیلابی پانی میں چلنے یا گاڑی چلانے سے گریز کریں۔\n"
                "۳. بجلی کا مین سوئچ بند کریں۔\n"
                "۴. ہنگامی کٹ تیار رکھیں: پانی، کھانا، دستاویزات، ٹارچ۔\n\n"
                "ہیلپ لائن: پی ڈی ایم اے کے پی: 1700\n"
                "ماخذ: قومی ادارہ برائے آفات (این ڈی ایم اے)"
            ),
        ]
        for i, text in enumerate(content_pages):
            page = doc.new_page()
            page.insert_text((50, 50), text, fontsize=11)

        demo_path = RAW_DIR / "ndma_chitral_advisory_demo.pdf"
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        doc.save(str(demo_path))
        doc.close()
        print(f"Created demo PDF: {demo_path}")
    except Exception as e:
        print(f"Could not create demo PDF: {e}")


if __name__ == "__main__":
    main()
