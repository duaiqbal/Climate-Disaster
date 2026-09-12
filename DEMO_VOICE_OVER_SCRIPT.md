# ChitralSafe — Demo Voice-Over Script
## Panel Presentation (5-7 Minutes)

**Presenter:** Tooba Iqbal (or any team member)  
**Demo URL:** http://localhost:8080  
**Language:** English (with Urdu terms where appropriate)

---

## 🎬 OPENING (30 seconds)

**[Screen: Show dashboard/landing]**

> "Good morning, respected panel members. I'm Tooba Iqbal, and today I'm presenting **ChitralSafe** — an offline-first disaster decision support system designed for flood and landslide-prone communities in Chitral, Khyber Pakhtunkhwa.
>
> The core problem we're solving is this: during disasters, electricity and internet fail **exactly when they're needed most**. Official NDMA and PDMA advisories become inaccessible. Our system works with **zero internet, zero electricity** — using only a charged phone or tablet."

---

## 🎬 SCENE 1: Dashboard Overview (45 seconds)

**[Screen: Main dashboard with hazard indicator]**

**[Action: Point to/hover over dashboard elements]**

> "This is our main dashboard. Notice three key elements:
>
> **First** — [point to greeting] — a personalized greeting that adapts based on user profile and time of day. This isn't hardcoded — it pulls from local storage.
>
> **Second** — [point to hazard card] — a location-based hazard indicator. Using GPS coordinates, we query a precomputed grid of **10,000 cells** covering the entire Chitral region. Each cell has slope analysis and river proximity data. Right now, it's showing **HIGH risk** because our simulated location is in a flood-prone valley.
>
> **Third** — [point to quick actions] — quick access to emergency features: Chat, Alerts, Safety Checklists, and Emergency Contacts.
>
> Everything you see here works **completely offline**. No backend calls, no internet required."

---

## 🎬 SCENE 2: Offline Q&A with RAG (90 seconds)

**[Screen: Navigate to Chat screen]**

**[Action: Type "What should I do during a flood?" and send]**

> "Now let me demonstrate our **Retrieval-Augmented Generation system**.
>
> I'm asking: 'What should I do during a flood?'
>
> [Wait for response]
>
> Notice what just happened. The system searched our local SQLite database containing **315 verified document chunks** from NDMA, PDMA Khyber Pakhtunkhwa, and Pakistan Meteorological Department. These are **official, fact-checked sources** — not web-scraped content.
>
> [Point to answer on screen]
>
> The answer you see combines **retrieval** with optional **generation**. By default, we use retrieval-only mode — pure keyword matching, no AI fabrication. But we've also integrated **Llama3 via Ollama** — a local large language model that can rephrase these chunks into natural language.
>
> [Point to source attribution at bottom]
>
> And here's the critical part: **every answer shows its source**. You can see the organization — NDMA — the document title, publication date, and evidence level. This is **Constraint 5** in our architecture: if retrieval confidence is too low, the system **refuses to answer** rather than fabricating.
>
> Let me try another query in **Roman Urdu** to show multilingual support."

**[Action: Type "Flood mein kya karein?" and send]**

> "[Wait for response]
>
> The system normalized the spelling variants — 'karein' could also be 'karin' or 'karain' — and retrieved the same verified guidance. This works because we preprocess Roman Urdu with 47 known spelling variants.
>
> Everything I just showed you worked **without internet**. The database is bundled with the app."

---

## 🎬 SCENE 3: Real-Time Alert Monitoring (60 seconds)

**[Screen: Navigate to Alerts tab]**

**[Action: Pull down to refresh alerts]**

> "Next, our **real-time alert monitoring system**.
>
> [Pull to refresh]
>
> We're now syncing with our FastAPI backend. The backend runs an **APScheduler job** that scrapes the official NDMA website every **6 hours**. I know what you're thinking — why not real-time?
>
> [Point to screen]
>
> Because NDMA has no public API. We scrape their HTML. And disasters don't evolve minute-by-minute — they evolve over hours. NDMA typically posts 1-2 major alerts per day. Six-hour polling is optimal for resource usage and reliability.
>
> [Point to alert card if visible]
>
> Each alert shows:
> - **Source organization** — NDMA, PDMA, or PMD
> - **Verification status** — PUBLISHED means it's been verified by our system
> - **Timestamp** — when it was published
> - **Affected regions** — so users know if it applies to them
>
> Alerts go through a lifecycle: **DISCOVERED → VERIFIED → PUBLISHED**. This isn't just a dump of scraped data — we validate, deduplicate, and audit every change."

---

## 🎬 SCENE 4: Hazard Map (45 seconds)

**[Screen: Navigate to Map screen]**

**[Action: Show map with GPS marker and hazard overlay]**

> "This is our **hazard assessment map**.
>
> [Point to your location marker]
>
> The blue marker is the current GPS location — simulated for this demo, but on a real device, this would be live GPS data.
>
> [Point to hazard cells/shading]
>
> The colored regions represent our precomputed hazard grid. We processed **Copernicus DEM elevation data** and **OpenStreetMap river networks** to calculate two factors:
> 1. **Slope** — steep terrain means landslide risk
> 2. **River proximity** — near rivers means flood risk
>
> Each of the 10,000 cells is classified as HIGH, MEDIUM, or LOW risk.
>
> [Tap on a cell if possible]
>
> When you tap a location, it shows the contributing factors and a clear disclaimer: this is a **coarse indicator based on terrain**, not a validated scientific prediction. We don't pretend this replaces official NDMA warnings."

---

## 🎬 SCENE 5: Safety Checklists (30 seconds)

**[Screen: Navigate to Safety/Go Bag screen]**

**[Action: Check/uncheck some items]**

> "Our **safety checklist system** helps users prepare before disasters strike.
>
> [Point to checklist items]
>
> This is the 'Go Bag' checklist — essentials to grab if you need to evacuate. Users can check items as they pack them. Progress is saved locally using SharedPreferences, so if they close the app and come back, their progress is preserved.
>
> We have similar checklists for flood preparedness, landslide safety, and evacuation procedures — all based on official NDMA guidelines."

---

## 🎬 SCENE 6: Emergency Contacts (30 seconds)

**[Screen: Navigate to Emergency Contacts]**

**[Action: Tap on a contact to show call dialog]**

> "And finally, **emergency contacts**.
>
> [Point to numbers]
>
> These are Pakistan's actual emergency numbers:
> - **1122** — Rescue Services (we fixed a bug — it was 112, which is Europe)
> - **100** — Police
> - **101** — Fire
> - **1078** — NDMA Helpline
> - **1077** — PDMA KP Helpline
>
> [Tap one]
>
> Users can dial directly from the app. During a disaster, when seconds matter, this one-tap calling can save lives."

---

## 🎬 SCENE 7: Backend API Demo (60 seconds - OPTIONAL)

**[Screen: Switch to http://localhost:8002/docs]**

> "Let me quickly show you our backend architecture.
>
> [Open API docs page]
>
> This is our **FastAPI backend** with interactive documentation. Here you can see all our endpoints:
>
> [Scroll through endpoints]
>
> - `/rag/query` — the RAG endpoint I showed you
> - `/alerts` — real-time alert CRUD
> - `/monitor/run` — manual trigger for alert scraping
> - `/monitor/status` — check scheduler status
> - `/knowledge/search` — raw retrieval without AI
>
> [Click on /monitor/status and 'Try it out']
>
> Let me show the scheduler status live.
>
> [Execute]
>
> [Point to response]
>
> You can see:
> - **running: true** — the scheduler is active
> - **next_run** — when it will scrape NDMA next
> - **last_run** — the last successful run
>
> This is how we achieve 'real-time' alerts within the constraints of having no official API."

---

## 🎬 TECHNICAL DEEP DIVE (90 seconds)

**[Screen: Can show IDE with code, or just talk while showing dashboard]**

> "Let me address the technical architecture briefly.
>
> **Data Pipeline:**
> We built a three-stage pipeline:
> 1. **Extract** — PDFs from NDMA/PDMA using PyMuPDF
> 2. **Chunk** — paragraph-level chunks with 80-character overlap
> 3. **Package** — bundle into SQLite databases for offline use
>
> The result: **knowledge.sqlite** with 315 chunks, 216 KB. That's the entire knowledge base fitting in less space than a single photo.
>
> **RAG Architecture:**
> Our RAG system has two layers:
> - **Retrieval** (mandatory) — SQLite LIKE queries, works offline
> - **Generation** (optional) — Llama3 via Ollama, rephrases text
>
> Generation is **never allowed to invent facts**. We enforce two constraints:
> - **Constraint 5:** If retrieval score is below threshold, refuse to answer
> - **Constraint 6:** The LLM provider is fully swappable — set `LLM_PROVIDER=none` and you get pure retrieval, set `=ollama` and you get natural language
>
> **Alert Monitoring:**
> The scheduler runs as an **APScheduler AsyncIO job** inside FastAPI's lifespan. It spawns `official_alert_monitor.py` as a subprocess, which:
> 1. Fetches NDMA HTML
> 2. Parses with BeautifulSoup
> 3. Detects changes via content hashing
> 4. POSTs new alerts to our database
> 5. Logs everything in `alert_history` for audit trail
>
> **Testing:**
> - 50 backend tests passing — all CRUD, lifecycle, auth
> - 26 Flutter widget tests passing
> - Retrieval evaluation: **Precision@5 = 1.0** on 20 test queries (self-constructed ground truth)"

---

## 🎬 HONEST LIMITATIONS (45 seconds)

**[Screen: Back to dashboard or stay on current screen]**

> "Now let me be completely honest about our limitations, because that's what good engineering requires.
>
> **What we DON'T claim:**
> - This is **not** a prediction model. We don't predict when disasters will occur.
> - This is **not** an official alert system. We aggregate official sources, we don't create alerts.
> - Our hazard grid is based on **terrain modeling**, not validated field sensors.
> - We have **no real-time NDMA API** — we scrape their website.
> - The knowledge base has **315 chunks** — not 10,000. It's a seed build.
> - We use **SharedPreferences** for token storage — for production, we'd upgrade to flutter_secure_storage.
>
> **What we DO provide:**
> A reliable, offline-first system that makes existing verified guidance **accessible, location-aware, and understandable** during disasters when electricity and internet fail.
>
> We document all of this honestly in our `PROJECT_STATUS.md` and `INTEGRATION_STATUS.md` files."

---

## 🎬 COMPETITIVE DIFFERENTIATION (30 seconds)

**[Screen: Dashboard]**

> "How is ChitralSafe different from existing disaster apps?
>
> **FEMA Mobile** (USA) — Requires internet. Alerts need connectivity.
> 
> **Red Cross Emergency** — Partially offline, but limited to pre-loaded PDFs. No location-aware hazard assessment.
>
> **NDMA's website** — Not a mobile app. Not offline. Not location-aware.
>
> **ChitralSafe** — Combines offline Q&A, location hazard assessment, real-time alerts (when online), and Pakistan-specific content — all in one system designed for rural, low-connectivity contexts."

---

## 🎬 CLOSING (30 seconds)

**[Screen: Dashboard or app home screen]**

> "To summarize:
>
> **ChitralSafe** is an offline-first, multilingual disaster decision support system for Chitral communities.
>
> ✅ **315 verified NDMA/PDMA document chunks** — offline Q&A  
> ✅ **10,000 precomputed hazard cells** — GPS-based risk assessment  
> ✅ **Real-time alert scraping** — 6-hour polling from NDMA  
> ✅ **RAG with optional LLM** — Llama3 via Ollama, no fabrication  
> ✅ **Zero mandatory cloud APIs** — runs on a charged phone  
>
> Our code is fully documented, tested, and open on GitHub: **github.com/duaiqbal/Climate-Disaster**
>
> Thank you. I'm ready for questions."

---

## 🎬 Q&A PREPARATION

### Expected Questions & Answers:

**Q: "Is the AI real or fake?"**

**A:** "Both retrieval and generation are real. Retrieval uses SQLite keyword search — intentional for offline reliability. Generation uses Llama3, an 8-billion-parameter model running locally via Ollama. The system works without the LLM (set LLM_PROVIDER=none) — generation is an enhancement layer, not a dependency. I can show you the code right now — `backend/services/rag_service.py`, line 50."

---

**Q: "Why not use OpenAI?"**

**A:** "Three reasons: Cost — Ollama is free, OpenAI charges per token. Offline capability — Ollama runs locally, no internet needed. Privacy — no user queries sent to external servers. Our architecture is provider-agnostic — we support OpenAI and Groq too via environment variables. But Ollama is the production recommendation for disaster contexts where internet is unreliable."

---

**Q: "How do you validate the hazard grid?"**

**A:** "We don't claim it's validated — we explicitly document this as synthetic terrain modeling. The grid combines slope (from Copernicus DEM) and river proximity (from OpenStreetMap). It's a **coarse indicator**, not a replacement for official warnings. In production, this would require field validation with government geologists and comparison against historical disaster data. We show a clear disclaimer in the app."

---

**Q: "What if NDMA changes their website HTML?"**

**A:** "Our scraper would fail, and we'd need to update the parsing logic. This is why we built a modular fetcher architecture — `official_alert_monitor.py` can be swapped or updated independently. We log all scraping failures in `alert_history`, and admins can see errors via `/monitor/status`. The ideal solution is for NDMA to expose a public API, which we've documented as a limitation."

---

**Q: "Can this scale to other provinces?"**

**A:** "Absolutely. The architecture is province-agnostic. We'd need to:
1. Add PDMA Punjab, PDMA Sindh, PDMA Balochistan to the scraper
2. Expand the hazard grid to cover those regions
3. Ingest official documents from those provinces
4. Update the app name (ChitralSafe → KPSafe → PakSafe)

The code is designed for this — we use `source_org` and `affected_regions` fields throughout."

---

**Q: "Show me the code."**

**A:** [Open VS Code or GitHub]
"Here's the RAG service — `backend/services/rag_service.py`. Line 70-110 shows the provider dispatch table. Here's the scheduler — `backend/core/scheduler.py`, line 60 shows the APScheduler setup. Here's the Flutter chat integration — `app/lib/features/chat/chat_screen.dart`, line 60 shows the /rag/query API call."

---

## 🎬 DEMO SEQUENCE SUMMARY

**Total Time:** 5-7 minutes

| Scene | Duration | What to Show |
|-------|----------|------------|
| Opening | 30s | Problem statement |
| Dashboard | 45s | Hazard indicator, personalization |
| Chat/RAG | 90s | Offline Q&A, sources, multilingual |
| Alerts | 60s | Real-time monitoring, lifecycle |
| Map | 45s | Hazard grid, GPS |
| Checklists | 30s | Go Bag, progress saving |
| Emergency | 30s | 1122, one-tap calling |
| Backend (optional) | 60s | API docs, scheduler status |
| Technical | 90s | Architecture, constraints |
| Limitations | 45s | Honest assessment |
| Differentiation | 30s | vs FEMA, Red Cross |
| Closing | 30s | Summary, GitHub |

**Buffer for Q&A:** 3-5 minutes

---

## 📝 TIPS FOR DELIVERY

### Voice & Tone:
- ✅ Confident but not arrogant
- ✅ Technical but accessible
- ✅ Honest about limitations
- ✅ Show passion for the problem

### Body Language:
- ✅ Maintain eye contact with panel (not just screen)
- ✅ Point to screen when referencing features
- ✅ Use hand gestures for emphasis
- ✅ Don't read from script — internalize key points

### Technical Credibility:
- ✅ Use precise terms (RAG, APScheduler, SQLite)
- ✅ Mention file paths and line numbers
- ✅ Reference actual code when challenged
- ✅ Don't oversell — be honest about constraints

### Disaster Context:
- ✅ Emphasize "zero internet, zero electricity"
- ✅ Use real-world scenarios ("when floods cut power...")
- ✅ Show empathy for affected communities
- ✅ Connect features to actual disaster response needs

---

## 🎥 RECORDING TIPS (if pre-recording)

1. **Use OBS Studio** or screen recorder
2. **Record in 1080p** (1920×1080)
3. **Use external mic** for clear audio
4. **Test audio levels** before full recording
5. **Have backup recording** (record twice)
6. **Export as MP4** (H.264 codec)
7. **Keep under 10 minutes** (attention span)

---

## ✅ PRE-DEMO CHECKLIST

- [ ] Backend running on port 8002
- [ ] Flutter app running on port 8080
- [ ] Browser tabs ready (app + API docs)
- [ ] Script printed or on second screen
- [ ] Water bottle nearby
- [ ] Phone on silent
- [ ] Backup demo video ready (if technical issues)
- [ ] GitHub repository open in tab
- [ ] VS Code open with key files (optional)
- [ ] Practiced full demo 2-3 times

---

**Good luck with your presentation!** 🚀

You've built a technically solid, ethically honest, and socially impactful system. The panel will see that.
