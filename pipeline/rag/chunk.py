"""
pipeline/rag/chunk.py
=====================
Step 2: Split extracted pages into smaller, retrieval-friendly chunks.

Input:  data/extracted/*.json
Output: data/chunks/*.json  (one JSON file per source, list of chunk dicts)

Chunking strategy:
  - Split on double-newline (paragraph boundaries) first.
  - If a paragraph exceeds MAX_CHARS, split further on sentence boundaries.
  - Maintain a sliding overlap of OVERLAP_CHARS to avoid cutting context.
  - Each chunk carries full provenance metadata.

Each chunk dict:
{
    "chunk_id":      "ndma_flood_advisory_2023_c001",
    "source_file":   "ndma_flood_advisory_2023.pdf",
    "source_org":    "NDMA",
    "doc_title":     "NDMA Flood Advisory 2023",
    "pub_date":      "2023-07-15",
    "language":      "en",
    "page_num":      2,
    "chunk_index":   1,
    "chunk_text":    "...",
    "keywords":      "flood,evacuation,higher ground,...",
    "evidence_level":"official",
    "char_count":    312
}
"""

import json
import re
import sys
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
MAX_CHARS = 600        # target max characters per chunk
OVERLAP_CHARS = 80     # overlap between consecutive chunks
MIN_CHARS = 60         # discard chunks shorter than this

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
EXTRACTED_DIR = ROOT / "data" / "extracted"
CHUNKS_DIR = ROOT / "data" / "chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ── Disaster keyword list for indexing ─────────────────────────────────────────
KEYWORD_SEEDS = {
    "en": [
        "flood", "flash flood", "landslide", "evacuation", "higher ground",
        "emergency", "warning", "alert", "shelter", "go-bag", "river",
        "rainfall", "monsoon", "slope", "hazard", "risk", "safety",
        "NDMA", "PDMA", "PMD", "helpline", "relief", "preparedness",
    ],
    "ur": [
        "سیلاب", "لینڈ سلائیڈ", "نکاسی", "انخلاء", "اونچی جگہ",
        "ہنگامی", "الرٹ", "خطرہ", "بارش", "پہاڑ", "دریا", "مدد",
        "این ڈی ایم اے", "پی ڈی ایم اے",
    ],
    "ru": [
        "flood", "selab", "saib", "landslide", "khiskaao", "bachao",
        "nikalna", "paani", "baarish", "pahar", "darya", "madad",
        "khatar", "hifazat", "alert",
    ],
}


def _extract_keywords(text: str, language: str) -> str:
    seeds = KEYWORD_SEEDS.get(language, KEYWORD_SEEDS["en"])
    found = set()
    lower_text = text.lower()
    for kw in seeds:
        if kw.lower() in lower_text:
            found.add(kw)
    return ",".join(sorted(found))


def _split_sentences(text: str) -> list[str]:
    # Split on sentence-ending punctuation
    parts = re.split(r"(?<=[.!?۔؟])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_paragraph(para: str, max_chars: int, overlap: int) -> list[str]:
    """Split a single paragraph into overlapping chunks of ≤ max_chars."""
    if len(para) <= max_chars:
        return [para]

    sentences = _split_sentences(para)
    chunks = []
    current = ""
    prev_tail = ""

    for sent in sentences:
        candidate = (prev_tail + " " + sent).strip() if prev_tail else sent
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
                # Keep overlap tail
                words = current.split()
                tail_words = []
                tail_len = 0
                for w in reversed(words):
                    if tail_len + len(w) + 1 <= overlap:
                        tail_words.insert(0, w)
                        tail_len += len(w) + 1
                    else:
                        break
                prev_tail = " ".join(tail_words)
            current = (prev_tail + " " + sent).strip() if prev_tail else sent

    if current:
        chunks.append(current)

    return chunks or [para[:max_chars]]


def chunk_document(doc: dict) -> list[dict]:
    source_file = doc["source_file"]
    source_org = doc["source_org"]
    doc_title = doc["doc_title"]
    pub_date = doc["pub_date"]
    language = doc["language"]
    # Propagate source_url from extract step (empty string for docs not in manifest)
    source_url = doc.get("source_url", "")

    # Determine evidence level from source
    evidence_map = {
        "NDMA": "official_national",
        "PDMA KP": "official_provincial",
        "PMD": "official_meteorological",
    }
    evidence_level = evidence_map.get(source_org, "official")

    stem = Path(source_file).stem
    all_chunks = []
    global_idx = 0

    for page in doc.get("pages", []):
        page_num = page["page_num"]
        page_text = page["text"].strip()
        if not page_text:
            continue

        # Split into paragraphs
        paragraphs = re.split(r"\n{2,}", page_text)
        for para in paragraphs:
            para = para.strip()
            if len(para) < MIN_CHARS:
                continue

            sub_chunks = _chunk_paragraph(para, MAX_CHARS, OVERLAP_CHARS)
            for sub in sub_chunks:
                if len(sub) < MIN_CHARS:
                    continue
                global_idx += 1
                chunk_id = f"{stem}_c{global_idx:04d}"
                keywords = _extract_keywords(sub, language)

                all_chunks.append({
                    "chunk_id":      chunk_id,
                    "source_file":   source_file,
                    "source_org":    source_org,
                    "doc_title":     doc_title,
                    "pub_date":      pub_date,
                    "language":      language,
                    "page_num":      page_num,
                    "chunk_index":   global_idx,
                    "chunk_text":    sub,
                    "keywords":      keywords,
                    "evidence_level": evidence_level,
                    "char_count":    len(sub),
                    "source_url":    source_url,   # ← new field
                })

    return all_chunks


def main():
    extracted_files = sorted(EXTRACTED_DIR.glob("*.json"))
    if not extracted_files:
        print(f"No extracted JSON files in {EXTRACTED_DIR}")
        print("Run extract.py first.")
        sys.exit(1)

    total_chunks = 0
    for fp in extracted_files:
        with open(fp, encoding="utf-8") as f:
            doc = json.load(f)

        chunks = chunk_document(doc)
        out_path = CHUNKS_DIR / fp.name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"{fp.name}: {len(chunks)} chunks → {out_path.name}")
        total_chunks += len(chunks)

    print(f"\nTotal chunks: {total_chunks}  (saved to {CHUNKS_DIR})")


if __name__ == "__main__":
    main()
