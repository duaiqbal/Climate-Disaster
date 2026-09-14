"""
pipeline/rag/translate_urdu.py
================================
Phase 3.5: Generate Urdu translation chunks from English chunks.

Approach: (b) — translated dataset, clearly labeled as derived content.
Each Urdu chunk gets:
  - language = "ur"
  - evidence_level = "translated"  (NOT "official" — honest labeling)
  - chunk_id = original_id + "_ur"
  - source_url preserved from original

Decision rationale: Official Urdu-language versions of the 13 NDMA/PDMA PDFs
were not found in a reliably downloadable form at the time of this pipeline run.
Machine translation is used as a starting point; evidence_level="translated"
flags these for human review and prevents them from being presented as equivalent
to the original official documents.

Roman Urdu: RomanUrduNormalizer in retrieval_engine.dart maps Roman Urdu queries
to English keywords, so Roman Urdu users retrieve against English chunks.
No separate Roman Urdu chunk set is generated — the normalizer handles it.

Usage:
    python pipeline/rag/translate_urdu.py [--db path/to/knowledge.sqlite]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_DEFAULT = ROOT / "offline_package" / "knowledge.sqlite"

# ── Manual spot-checked Urdu translations for key preparedness phrases ────────
# These are used to translate key sentences in chunks. Not exhaustive — they
# cover the most common disaster preparedness terms.
_EN_TO_UR: dict[str, str] = {
    "flood":                "سیلاب",
    "flash flood":          "اچانک سیلاب",
    "landslide":            "لینڈ سلائیڈ",
    "earthquake":           "زلزلہ",
    "evacuation":           "انخلاء",
    "higher ground":        "اونچی جگہ",
    "emergency kit":        "ہنگامی کٹ",
    "go-bag":               "گو-بیگ",
    "emergency contacts":   "ہنگامی رابطے",
    "Rescue 1122":          "ریسکیو 1122",
    "NDMA":                 "این ڈی ایم اے",
    "PDMA KP":              "پی ڈی ایم اے KP",
    "rainfall":             "بارش",
    "monsoon":              "مون سون",
    "warning":              "انتباہ",
    "advisory":             "مشورہ",
    "preparedness":         "تیاری",
    "relief":               "ریلیف",
    "shelter":              "پناہ گاہ",
    "documents":            "دستاویزات",
    "river":                "دریا",
    "slope":                "ڈھلوان",
    "glacier":              "گلیشیر",
    "Chitral":              "چترال",
}

# Limit to high-value chunks: those with phase != general or disaster != general
# to avoid generating low-quality translations of generic content
_SELECTED_DISASTER_TYPES = {"flood", "flash_flood", "landslide", "earthquake", "glof"}
_SELECTED_PHASES         = {"before", "during", "after"}


def _simple_translate(text: str) -> str:
    """
    Very simple term-substitution 'translation'. This is NOT a proper translation.
    It replaces key English terms with Urdu equivalents in otherwise English text.
    The result is a mixed-language text useful only as a retrieval bridge.
    Proper Urdu translation requires human review.
    """
    result = text
    for en, ur in _EN_TO_UR.items():
        result = result.replace(en, ur)
    return result


def generate_urdu_chunks(db_path: Path, limit: int = 100) -> int:
    """
    Generates Urdu translation chunks for high-value English chunks.
    Returns count of chunks added.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Add language index if not present
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_language ON chunks(language)")

    # Fetch high-value English chunks (phase+disaster classified)
    cur.execute("""
        SELECT chunk_id, source_org, doc_title, pub_date, page_num, chunk_index,
               chunk_text, keywords, char_count, source_url, disaster_type, phase
        FROM chunks
        WHERE language = 'en'
          AND (
            disaster_type IN ('flood','flash_flood','landslide','earthquake','glof')
            OR phase IN ('before','during','after')
          )
        ORDER BY chunk_id
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()

    inserted = 0
    for row in rows:
        ur_id = row["chunk_id"] + "_ur"

        # Skip if already exists
        existing = cur.execute("SELECT 1 FROM chunks WHERE chunk_id=?", (ur_id,)).fetchone()
        if existing:
            continue

        translated_text = _simple_translate(row["chunk_text"])
        translated_keywords = _simple_translate(row["keywords"] or "")

        cur.execute("""
            INSERT OR IGNORE INTO chunks
              (chunk_id, source_org, doc_title, pub_date, language,
               page_num, chunk_index, chunk_text, keywords, evidence_level,
               char_count, source_url, disaster_type, phase)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ur_id,
            row["source_org"],
            row["doc_title"],
            row["pub_date"],
            "ur",
            row["page_num"],
            row["chunk_index"],
            translated_text,
            translated_keywords,
            "translated",       # NOT "official" — clearly labeled derived content
            len(translated_text),
            row["source_url"] or "",
            row["disaster_type"],
            row["phase"],
        ))
        inserted += 1

    conn.commit()

    # Report
    cur.execute("SELECT language, COUNT(*) FROM chunks GROUP BY language")
    print("Chunk counts by language:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")
    print(f"\nInserted {inserted} new Urdu translation chunks.")
    print("NOTE: evidence_level='translated' — not equivalent to official documents.")
    print("Human review of translations is recommended before production use.")

    conn.close()
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_DEFAULT))
    parser.add_argument("--limit", type=int, default=100,
                        help="Max English chunks to translate (default 100)")
    args = parser.parse_args()
    generate_urdu_chunks(Path(args.db), args.limit)
