"""
evaluation/retrieval_eval.py
=============================
Computes Precision@K and Recall@K for the offline keyword retriever
across all three languages: English (en), Urdu (ur), Roman Urdu (ru).

Ground truth: evaluation/ground_truth_eval.json
Output:       evaluation/eval_summary.json  +  console report

Methodology:
  - Self-constructed ground truth (labeled by project team)
  - Each query has a set of relevant chunk_ids
  - Precision@K = |retrieved ∩ relevant| / K
  - Recall@K    = |retrieved ∩ relevant| / |relevant|
  - MRR         = mean reciprocal rank of first relevant result
  - Results are stratified by language AND hazard type

Honest limitations (per README):
  - Ground truth is self-constructed, not from an external benchmark
  - Roman Urdu results may be lower due to spelling variant coverage
  - All results including weak cases are reported transparently

Usage:
    python evaluation/retrieval_eval.py [--k 5] [--db path/to/knowledge.sqlite]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
GT_PATH   = ROOT / "evaluation" / "ground_truth_eval.json"
OUT_PATH  = ROOT / "evaluation" / "eval_summary.json"
DB_PATH   = ROOT / "offline_package" / "knowledge.sqlite"


# ── Retriever (mirrors app keyword logic) ─────────────────────────────────────

ROMAN_URDU_VARIANTS: dict[str, list[str]] = {
    "selab":    ["selab", "sailab", "sab", "sail"],
    "saib":     ["saib", "sab", "sayl"],
    "flood":    ["flood"],
    "landslide":["landslide", "khiskaao", "zameeni"],
    "bachao":   ["bachao", "bachaao"],
    "nikalna":  ["nikalna", "evacuation"],
    "paani":    ["paani", "pani"],
    "baarish":  ["baarish", "barish"],
    "khatar":   ["khatar", "khatara"],
}


def _expand_roman_urdu(query: str) -> str:
    tokens = query.lower().split()
    expanded = set()
    for token in tokens:
        found = False
        for variants in ROMAN_URDU_VARIANTS.values():
            if token in variants:
                expanded.update(variants)
                found = True
                break
        if not found:
            expanded.add(token)
    return " ".join(expanded)


def _tokenize(query: str) -> list[str]:
    import re
    return [t for t in re.split(r"[\s,،؛؟.!?;:()\[\]\"\']+", query.lower()) if len(t) >= 2]


def retrieve(conn: sqlite3.Connection, query: str, language: str, k: int) -> list[str]:
    """Returns list of chunk_ids (up to k)."""
    effective_query = _expand_roman_urdu(query) if language == "ru" else query
    # Roman Urdu fallback to English if language == 'ru'
    search_lang = language

    tokens = _tokenize(effective_query)
    if not tokens:
        return []

    like_clauses = " OR ".join("(chunk_text LIKE ? OR keywords LIKE ?)" for _ in tokens)
    score_expr   = " + ".join("CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END" for _ in tokens)
    args = [f"%{t}%" for t in tokens for _ in (0, 1)]
    score_args   = [f"%{t}%" for t in tokens]

    sql = f"""
        SELECT chunk_id, ({score_expr}) AS score
        FROM chunks
        WHERE language = ? AND ({like_clauses})
        ORDER BY score DESC
        LIMIT ?
    """
    rows = conn.execute(sql, score_args + [search_lang] + args + [k]).fetchall()

    # Fallback: if Roman Urdu returns nothing, try English
    if not rows and language == "ru":
        rows = conn.execute(sql, score_args + ["en"] + args + [k]).fetchall()

    return [r[0] for r in rows]


# ── Metrics ───────────────────────────────────────────────────────────────────

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    hits = sum(1 for r in retrieved[:k] if r in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for r in retrieved[:k] if r in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for i, r in enumerate(retrieved, start=1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


# ── Evaluation loop ───────────────────────────────────────────────────────────

def run_eval(k: int, db_path: Path) -> dict:
    if not GT_PATH.exists():
        print(f"ERROR: Ground truth file not found: {GT_PATH}")
        print("Run with --create-gt to generate a template, then fill in relevant_chunk_ids.")
        sys.exit(1)

    if not db_path.exists():
        print(f"ERROR: knowledge.sqlite not found: {db_path}")
        print("Run the data pipeline first: python pipeline/run_pipeline.py")
        sys.exit(1)

    with open(GT_PATH, encoding="utf-8") as f:
        ground_truth: list[dict] = json.load(f)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    results_by_lang:  dict[str, list[dict]] = {}
    results_by_hazard: dict[str, list[dict]] = {}
    all_results: list[dict] = []

    print(f"\n{'═'*70}")
    print(f"  Disaster DSS — Retrieval Evaluation  (K={k})")
    print(f"  Ground truth: {len(ground_truth)} queries")
    print(f"  Database:     {db_path}")
    print(f"{'═'*70}\n")

    for item in ground_truth:
        query      = item["query"]
        language   = item["language"]
        relevant   = set(item.get("relevant_chunk_ids", []))
        hazard     = item.get("hazard_type", "unknown")

        if not relevant:
            # Skip unannotated entries but report them
            print(f"  SKIP (no annotation): [{language}] {query[:60]}")
            continue

        retrieved = retrieve(conn, query, language, k)
        p = precision_at_k(retrieved, relevant, k)
        r = recall_at_k(retrieved, relevant, k)
        rr = reciprocal_rank(retrieved, relevant)
        f = f1(p, r)

        result = {
            "query": query,
            "language": language,
            "hazard_type": hazard,
            "relevant_count": len(relevant),
            "retrieved_count": len(retrieved),
            f"precision@{k}": round(p, 4),
            f"recall@{k}": round(r, 4),
            "mrr": round(rr, 4),
            "f1": round(f, 4),
            "retrieved_ids": retrieved,
        }
        all_results.append(result)

        # Bucket by language
        results_by_lang.setdefault(language, []).append(result)
        results_by_hazard.setdefault(hazard, []).append(result)

        # Per-query console output
        hit_marker = "✓" if p > 0 else "✗"
        print(f"  [{language}][{hazard}] {hit_marker} P@{k}={p:.2f} R@{k}={r:.2f} MRR={rr:.2f} | {query[:55]}")

    conn.close()

    # ── Aggregate by language ─────────────────────────────────────────────────
    def _avg(lst: list[dict], metric: str) -> float:
        vals = [x[metric] for x in lst if metric in x]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    lang_summary: dict[str, dict] = {}
    for lang, items in results_by_lang.items():
        lang_summary[lang] = {
            "queries": len(items),
            f"precision@{k}": _avg(items, f"precision@{k}"),
            f"recall@{k}":    _avg(items, f"recall@{k}"),
            "mrr":            _avg(items, "mrr"),
            "f1":             _avg(items, "f1"),
        }

    hazard_summary: dict[str, dict] = {}
    for hz, items in results_by_hazard.items():
        hazard_summary[hz] = {
            "queries": len(items),
            f"precision@{k}": _avg(items, f"precision@{k}"),
            f"recall@{k}":    _avg(items, f"recall@{k}"),
            "mrr":            _avg(items, "mrr"),
        }

    overall = {
        "queries": len(all_results),
        f"precision@{k}": _avg(all_results, f"precision@{k}"),
        f"recall@{k}":    _avg(all_results, f"recall@{k}"),
        "mrr":            _avg(all_results, "mrr"),
        "f1":             _avg(all_results, "f1"),
    }

    # ── Console report ────────────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  RESULTS BY LANGUAGE")
    print(f"{'─'*70}")
    for lang, s in lang_summary.items():
        print(f"  {lang:4s}  queries={s['queries']:3d}  "
              f"P@{k}={s[f'precision@{k}']:.3f}  "
              f"R@{k}={s[f'recall@{k}']:.3f}  "
              f"MRR={s['mrr']:.3f}  F1={s['f1']:.3f}")

    print(f"\n{'─'*70}")
    print(f"  RESULTS BY HAZARD TYPE")
    print(f"{'─'*70}")
    for hz, s in hazard_summary.items():
        print(f"  {hz:15s}  queries={s['queries']:3d}  "
              f"P@{k}={s[f'precision@{k}']:.3f}  "
              f"R@{k}={s[f'recall@{k}']:.3f}  "
              f"MRR={s['mrr']:.3f}")

    print(f"\n{'═'*70}")
    print(f"  OVERALL  queries={overall['queries']}  "
          f"P@{k}={overall[f'precision@{k}']:.3f}  "
          f"R@{k}={overall[f'recall@{k}']:.3f}  "
          f"MRR={overall['mrr']:.3f}  F1={overall['f1']:.3f}")
    print(f"{'═'*70}\n")

    summary = {
        "k": k,
        "overall": overall,
        "by_language": lang_summary,
        "by_hazard_type": hazard_summary,
        "per_query": all_results,
        "honest_limitations": [
            "Ground truth is self-constructed by the project team, not an external benchmark.",
            "Roman Urdu results reflect real spelling-variant coverage gaps where they exist.",
            "Precision@K is bounded by K — low P does not always mean low relevance quality.",
            "Recall is bounded by the number of annotated relevant chunks per query.",
        ],
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  Full results saved: {OUT_PATH}")

    return summary


# ── Ground-truth template generator ──────────────────────────────────────────

def create_gt_template(db_path: Path) -> None:
    """Writes a starter ground_truth_eval.json with queries pre-filled."""
    template_queries = [
        # English — flood
        {"query": "What should I do during a flood?",             "language": "en", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "Flood evacuation procedure",                   "language": "en", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "Flash flood warning signs",                    "language": "en", "hazard_type": "flash_flood","relevant_chunk_ids": []},
        {"query": "How to prepare a go-bag",                      "language": "en", "hazard_type": "preparedness","relevant_chunk_ids": []},
        {"query": "Do not walk through floodwater",               "language": "en", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "Turn off electricity before evacuation",       "language": "en", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "NDMA flood advisory Chitral",                  "language": "en", "hazard_type": "flood",      "relevant_chunk_ids": []},
        # English — landslide
        {"query": "Landslide warning signs",                      "language": "en", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        {"query": "Cracks in ground landslide risk",              "language": "en", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        {"query": "PDMA KP landslide advisory",                   "language": "en", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        {"query": "Move away from landslide path",                "language": "en", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        # English — preparedness
        {"query": "Emergency kit contents",                       "language": "en", "hazard_type": "preparedness","relevant_chunk_ids": []},
        {"query": "Monsoon season preparedness Pakistan",         "language": "en", "hazard_type": "preparedness","relevant_chunk_ids": []},
        {"query": "PDMA KP helpline number",                      "language": "en", "hazard_type": "preparedness","relevant_chunk_ids": []},
        # Urdu — flood
        {"query": "سیلاب کے دوران کیا کریں",                     "language": "ur", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "سیلاب سے پہلے تیاری",                         "language": "ur", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "اونچی جگہ پر جائیں",                          "language": "ur", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "ہنگامی کٹ تیار کریں",                         "language": "ur", "hazard_type": "preparedness","relevant_chunk_ids": []},
        # Urdu — landslide
        {"query": "لینڈ سلائیڈ کی علامات",                       "language": "ur", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        {"query": "زمین میں دراڑ لینڈ سلائیڈ",                   "language": "ur", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        # Roman Urdu — flood
        {"query": "Flood mein kya karein",                        "language": "ru", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "Selab se bachne ka tarika",                    "language": "ru", "hazard_type": "flood",      "relevant_chunk_ids": []},
        {"query": "Achanak selab ki nishanian",                   "language": "ru", "hazard_type": "flash_flood","relevant_chunk_ids": []},
        {"query": "Go-bag mein kya rakhein",                      "language": "ru", "hazard_type": "preparedness","relevant_chunk_ids": []},
        {"query": "Paani aane pe ghar chhorein",                  "language": "ru", "hazard_type": "flood",      "relevant_chunk_ids": []},
        # Roman Urdu — landslide
        {"query": "Zameeni khiskaav ke signs",                    "language": "ru", "hazard_type": "landslide",  "relevant_chunk_ids": []},
        {"query": "Pahaar se dur raho baarish mein",              "language": "ru", "hazard_type": "landslide",  "relevant_chunk_ids": []},
    ]

    # Auto-fill relevant_chunk_ids by running retrieval at K=5 against the DB
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        for item in template_queries:
            retrieved = retrieve(conn, item["query"], item["language"], k=5)
            item["relevant_chunk_ids"] = retrieved  # start from retrieved; annotator adjusts
            item["_annotation_note"] = (
                "AUTO-PREFILLED from K=5 retrieval. "
                "Review and correct relevant_chunk_ids before using for eval."
            )
        conn.close()
        print(f"Auto-prefilled {len(template_queries)} queries with K=5 retrieval results.")
        print("IMPORTANT: Review each entry and correct relevant_chunk_ids manually.")
    else:
        print(f"DB not found at {db_path} — template written without auto-fill.")

    with open(GT_PATH, "w", encoding="utf-8") as f:
        json.dump(template_queries, f, ensure_ascii=False, indent=2)
    print(f"Ground truth template: {GT_PATH}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Disaster DSS Retrieval Evaluation")
    parser.add_argument("--k",        type=int,  default=5,       help="Cutoff K (default 5)")
    parser.add_argument("--db",       type=str,  default=str(DB_PATH), help="Path to knowledge.sqlite")
    parser.add_argument("--create-gt",action="store_true",         help="Generate ground truth template")
    args = parser.parse_args()

    db_path = Path(args.db)

    if args.create_gt:
        create_gt_template(db_path)
    else:
        run_eval(k=args.k, db_path=db_path)
