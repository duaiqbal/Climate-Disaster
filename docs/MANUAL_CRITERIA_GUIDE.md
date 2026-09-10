# Manual Criteria Guide — Knowledge Source Evaluation

This guide defines the criteria used to decide whether a document or advisory is eligible for inclusion in the Disaster DSS offline knowledge base.

All ingested content must be manually reviewed against these criteria before running the pipeline. Automated scraping (e.g. `fetchers/ndma_scraper.py`) produces candidates only — human review is always required.

---

## Inclusion Criteria

A document or advisory is eligible for inclusion if it meets **all** of the following:

### C1 — Source Authority

The content must originate from one of the approved authoritative sources:

| Organisation | Type | Scope |
|-------------|------|-------|
| NDMA Pakistan | National disaster authority | All hazards, national |
| PDMA KP | Provincial disaster authority | All hazards, Khyber Pakhtunkhwa |
| PMD Pakistan | National meteorological authority | Weather, seasonal outlooks |

Content from NGOs, news outlets, social media, or unofficial sources is **not eligible**, regardless of accuracy.

### C2 — Geographic Relevance

The content must be relevant to at least one of:
- Chitral district
- Upper Chitral district
- Northern Khyber Pakhtunkhwa (applicable to Chitral)
- National-level guidance applicable to Chitral's hazard context (flood, landslide)

Out-of-scope content (e.g. Karachi cyclone guidance) must be excluded even if it comes from an authorised source.

### C3 — Hazard Relevance

Content must relate to one or more in-scope hazards:
- **Flood** (including monsoon flooding)
- **Flash flood**
- **Landslide** (including mudslide, rock fall)
- **General preparedness** directly applicable to the above hazards

Out-of-scope hazards (GLOF, earthquake, drought) may be included only if they appear within a broader flood/landslide advisory. They must not form the primary topic of an included chunk.

### C4 — Actionability

The content must contain at least one of:
- Specific action guidance ("Move to higher ground", "Turn off electricity")
- Preparedness instructions ("Prepare a go-bag with…")
- Warning signs ("Cracks in the ground indicate…")
- Official contact information (helpline numbers, relief camp locations)

Background information, historical statistics, or general descriptions without actionable guidance should be excluded.

### C5 — Recency

- Prefer documents from 2020 onwards
- Documents older than 2015 require explicit justification for inclusion
- Advisory content dated "unknown" must still pass all other criteria and have its source clearly labeled

### C6 — Language

Accepted languages:
- **English** — primary
- **Urdu** — accepted for Urdu-language official documents
- **Roman Urdu** — not a source language; Roman Urdu support is achieved via query-time normalisation, not separate Roman Urdu documents

---

## Exclusion Criteria

A document is **excluded** if any of the following apply:

| Code | Criterion |
|------|-----------|
| E1 | Source is unofficial (news, blog, social media, NGO without official mandate) |
| E2 | Content is geographically irrelevant to Chitral / northern KP |
| E3 | Hazard type is out of scope (GLOF-only, earthquake-only, etc.) |
| E4 | Content is purely statistical or historical with no actionable guidance |
| E5 | Content cannot be traced to a verifiable official publication |
| E6 | Content has been superseded by a newer advisory from the same source and the outdated content could cause harm if followed |
| E7 | Content was machine-translated without human verification |

---

## Evidence Levels

Each included chunk is assigned one of the following evidence levels:

| Level | Label in DB | Meaning |
|-------|-------------|---------|
| 1 | `official_national` | Directly from NDMA national advisory |
| 2 | `official_provincial` | Directly from PDMA KP advisory |
| 3 | `official_meteorological` | Directly from PMD official bulletin |
| 4 | `official` | Official source, specific tier not determinable |

Evidence level is assigned in `pipeline/rag/extract.py` via `SOURCE_REGISTRY` and must match the actual source document.

---

## Review Workflow

When adding a new source document:

1. **Obtain the original PDF** from the official source website (NDMA, PDMA KP, PMD)
2. **Record the URL and download date** in a comment in `pipeline/rag/extract.py` SOURCE_REGISTRY
3. **Apply criteria C1–C6** — document the decision in your pull request description
4. **Place the PDF in `data/raw/`** — never commit to the repo (gitignored)
5. **Run the pipeline** — `python pipeline/run_pipeline.py`
6. **Spot-check chunks** — review `data/chunks/` output, verify no exclusion criteria triggered
7. **Add evaluation queries** — add at least 3 new queries to `data/ground_truth_eval.json` covering the new content
8. **Run evaluation** — `python evaluation/retrieval_eval.py --k 5` — confirm no language regressions
9. **Update manifest** — bump `version` in `offline_package/manifest.json`
10. **Submit PR** with evaluation diff in the description

---

## Chunk Quality Checks

After chunking, manually verify a random 10% sample against these checks:

| Check | Pass condition |
|-------|---------------|
| Coherence | Chunk reads as a complete thought without requiring surrounding context |
| Length | 60–600 characters |
| Keyword coverage | At least one disaster keyword present in `keywords` field |
| Language accuracy | `language` field matches actual script |
| Source accuracy | `source_org` matches the document it was extracted from |
| No truncation | Chunk does not end mid-sentence if avoidable |

Chunks failing coherence or source accuracy checks must be corrected by adjusting chunking parameters or the source registry metadata.

---

## Evaluation Acceptance Thresholds

These are **guidance targets**, not hard pass/fail gates. Results below these targets must be disclosed and investigated, not suppressed.

| Language | Metric | Target |
|----------|--------|--------|
| English | Precision@5 | ≥ 0.40 |
| English | Recall@5 | ≥ 0.50 |
| English | MRR | ≥ 0.50 |
| Urdu | Precision@5 | ≥ 0.30 |
| Urdu | Recall@5 | ≥ 0.40 |
| Roman Urdu | Precision@5 | ≥ 0.25 |
| Roman Urdu | Recall@5 | ≥ 0.35 |

Roman Urdu targets are intentionally lower to reflect the inherent difficulty of spelling-variant coverage. Results at or below 0.20 Precision@5 for Roman Urdu must trigger a review of `RomanUrduNormalizer._variants`.

---

## Honest Reporting Policy

The Disaster DSS project is committed to transparent reporting of limitations:

- Evaluation results **including weak cases** are always reported in full
- Roman Urdu retrieval quality is measured, not assumed
- The hazard grid is always labeled as a coarse indicator
- Ground truth is labeled as self-constructed in all outputs
- No result is suppressed or cherry-picked for external presentation
