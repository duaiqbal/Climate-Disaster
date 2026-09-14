# ChitralSafe — Architecture Document

**Version:** 2.1.0 (Phase 2 — Multi-source alerts + location filtering)  
**Updated:** 2026-09-14

---

## 1. Project Scope

ChitralSafe is an **offline-first disaster decision-support system** focused on
**Chitral, Khyber Pakhtunkhwa, Pakistan**.

The alert feed is national (all of Pakistan) so users see alerts from Punjab,
Sindh, NDMA, and PMD — but:

- The **default view filters alerts to the user's location** (GPS or KP province).
- The **hazard grid, knowledge base, and preparedness guidance** remain
  Chitral/KP-specific and are not diluted by national data.
- Users can switch to "Show all Pakistan" to see the national picture.

This is consistent with the original project brief: Chitral-first design,
national alert coverage as an available broader view, not the default framing.

---

## 2. Official Alert Source Integration

### 2.1 Integrated Sources (verified reachable 2026-09-14)

| Source ID | Authority | Province/Scope | Page URL | Notes |
|---|---|---|---|---|
| `ndma_advisories` | NDMA | Pakistan (national) | `ndma.gov.pk/advisories/` | PDF links under `/storage/advisories/` |
| `ndma_sitreps` | NDMA | Pakistan (national) | `ndma.gov.pk/situation-reports/` | Monsoon situation reports |
| `ndma_guidelines` | NDMA | Pakistan (national) | `ndma.gov.pk/guidelines/` | DRM guidelines and plans |
| `pdma_kp` | PDMA KP | Khyber Pakhtunkhwa | `pdma.gov.pk/alerts-and-warnings/` | Primary KP source; covers Chitral directly |
| `pdma_punjab` | PDMA Punjab | Punjab | `pdma.punjab.gov.pk/weather-alerts/advisories` | PDF advisories under `/system/files/` |
| `pmd_ffd` | PMD Flood Forecasting Division | Pakistan (national) | `ffd.pmd.gov.pk/bulletins` | Real flood bulletins, `/bulletin/N/download` pattern |

All sources use the same ingestion pipeline:
```
Fetch listing page → parse PDF links → download → extract text →
classify hazard/severity → dedupe → POST /alerts with province field
```

Each source runs **independently** — one failure does not abort others.

### 2.2 Not Currently Integrated

| Authority | Reason | What to do if needed |
|---|---|---|
| **PDMA Sindh** | `pdma.sindh.gov.pk` exists but has no stable public PDF listings page — content is JS-rendered or behind login. | Monitor for a public alerts RSS or PDF listing page in future versions. |
| **PDMA Balochistan** | No verifiable official `pdma.balochistan.gov.pk` domain found. A `government-of-balochis.vercel.app` mock exists but is not authoritative. | Wait for an official domain to be established. |
| **GB-DMA** (Gilgit-Baltistan) | No dedicated GB-DMA public website. GB alerts are covered by NDMA national advisories (which are already integrated). | NDMA already covers GB explicitly (verified in NDMA advisory PDFs). |
| **AJK-SDMA** (Azad Kashmir) | No public-facing SDMA website with a scrapable alerts page. AJK alerts are covered by NDMA national advisories. | Same as GB-DMA — NDMA national source covers AJK. |
| **ICT** (Islamabad Capital Territory) | No separate ICT-DMA website. ICT is covered by NDMA national alerts. | NDMA national source covers ICT. |
| **PMD main site** (`weather.gov.pk`) | New PMD domain uses a JS-rendered SPA with no stable static PDF listing. | Integrate PMD FFD (`ffd.pmd.gov.pk`) instead — already done above. |

---

## 3. Location Filtering (Phase 2.3)

`GET /alerts` supports three filter modes, all optional and combinable:

```
?district=Chitral               → ILIKE string match (original behaviour)
?province=Khyber+Pakhtunkhwa    → exact province match (new)
?lat=35.85&lon=71.78&radius_km=100  → Haversine radius filter (new)
```

### Response field `location_match_type`

Every alert in `GET /alerts` now includes `location_match_type`:

| Value | Meaning |
|---|---|
| `"coordinate"` | Alert has lat/lon and is within the requested radius |
| `"district_name"` | Alert matched via district ILIKE (no exact coordinates) |
| `"province_only"` | Alert matched via province only |
| `"national"` | Alert has no location data (district="Pakistan") — shown for all queries |

**Alerts without lat/lon** fall back to province/district string matching rather
than being silently excluded. The `location_match_type` field makes this fallback
visible in the UI so precision is never overstated.

### Flutter default behaviour (Phase 2.3)

- Default: passes `?province=Khyber Pakhtunkhwa` (or GPS radius if available).
- User can toggle "Show all Pakistan" → no location filter → all active alerts shown.
- Alert cards show a small location precision label based on `location_match_type`.

---

## 4. Offline Package

| File | Contents | Size |
|---|---|---|
| `knowledge.sqlite` | 315 text chunks from 13 NDMA/PDMA PDFs + 1 synthetic demo | 216 KB |
| `hazard_grid.sqlite` | 10,000 hazard cells covering Chitral (100×100 at 0.01°) | — |

Both files are bundled inside the Flutter app binary and work with **zero internet**.

### Knowledge base scope

All 315 chunks are **English only** (Phase 3 adds Urdu translations).
Urdu and Roman Urdu queries fall back to English retrieval via `RomanUrduNormalizer`.

---

## 5. Backend Port

Default: **8002**  
Configured via `.env` `BACKEND_URL=http://127.0.0.1:8002`  
All callers (scheduler, monitor router, Flutter app, alert service) use 8002.

---

## 6. Alert Lifecycle

```
DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED
```

- Fetcher-sourced alerts enter at **DISCOVERED**.
- Advancing beyond DISCOVERED requires a separate verification step (admin API).
- EXPIRED alerts are deactivated (`is_active=False`).
- Every transition appends an immutable row to `alert_history`.

---

## 7. Phase Roadmap

| Phase | Status | Key deliverables |
|---|---|---|
| Phase 1 | ✅ Complete | Port bug, broken SQL, schema drift, payload gaps — 20/20 tests |
| Phase 2 | ✅ Complete | Multi-source alerts (6 integrated), per-source health, radius filter |
| Phase 3 | 🔄 In progress | Retrieval-first RAG, disaster_type/phase metadata, FAISS, Urdu KB |
| Phase 4 | 🔄 In progress | Grounded LLM generation, caching, adversarial testing |
