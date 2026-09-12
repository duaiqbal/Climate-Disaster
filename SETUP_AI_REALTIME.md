# Setup Guide: AI Model + Real-Time Alerts

## Part 1: Enable Local AI Model (Ollama)

### Step 1: Install Ollama

**Windows:**
```powershell
# Download from: https://ollama.com/download/windows
# Or use winget:
winget install Ollama.Ollama
```

**Linux/Mac:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull Llama 3 Model

```powershell
ollama pull llama3
```

This downloads ~4.7GB model. Wait for completion.

### Step 3: Verify Ollama is Running

```powershell
# Check service:
curl http://localhost:11434/api/tags

# You should see:
# {"models":[{"name":"llama3:latest",...}]}
```

### Step 4: Configure Backend to Use Ollama

Create `.env` file in `backend/` folder:

```env
# AI Model Configuration
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434/v1
LLM_MIN_CONFIDENCE=1
LLM_MAX_TOKENS=400

# Real-Time Alert Configuration  
MONITOR_ENABLED=1
MONITOR_INTERVAL_HOURS=6
```

### Step 5: Test RAG with AI

```powershell
cd backend
python -m pytest tests/test_knowledge_sync.py::test_rag_query_endpoint -v
```

**Expected output:**
```
tests/test_knowledge_sync.py::test_rag_query_endpoint PASSED
```

### Step 6: Test AI from Flutter App

1. Start backend:
```powershell
cd backend
python -m uvicorn main:app --reload --port 8002
```

2. Open Flutter app in Chrome (http://localhost:8080)
3. Go to Chat screen
4. Ask: "What should I do during heavy rain?"
5. You should get a natural language answer (not raw text chunks)

---

## Part 2: Enable Real-Time Alert Scraping

### Current Status
✅ Scheduler exists (`backend/core/scheduler.py`)  
✅ NDMA scraper exists (`fetchers/official_alert_monitor.py`)  
✅ APScheduler configured  
❌ **Currently runs every 6 hours (passive)**  

### Step 1: Verify Scheduler Configuration

In `backend/.env`:
```env
MONITOR_ENABLED=1
MONITOR_INTERVAL_HOURS=6
BACKEND_URL=http://127.0.0.1:8002
ADMIN_API_KEY=disaster-dss-dev-key-change-in-prod
```

### Step 2: Start Backend with Scheduler

```powershell
cd backend
$env:ENV="development"
python -m uvicorn main:app --reload --port 8002
```

**Check logs — you should see:**
```
INFO:     Scheduler started (next run: 2025-XX-XX XX:XX:XX UTC)
```

### Step 3: Manual Trigger (for Testing)

```powershell
# Trigger monitor immediately:
curl -X POST http://localhost:8002/monitor/run -H "X-Admin-API-Key: disaster-dss-dev-key-change-in-prod"

# Check status:
curl http://localhost:8002/monitor/status -H "X-Admin-API-Key: disaster-dss-dev-key-change-in-prod"
```

**Expected response:**
```json
{
  "running": true,
  "next_run": "2025-XX-XX XX:XX:XX+00:00",
  "status": "ok",
  "run_at": "2025-XX-XX XX:XX:XX+00:00",
  "returncode": 0
}
```

### Step 4: Check Ingested Alerts

```powershell
# View all alerts:
curl http://localhost:8002/alerts?active_only=true

# Expected:
{
  "alerts": [
    {
      "alert_id": "ndma-2025-001",
      "title": "Heavy Rainfall Alert - KP",
      "source_org": "NDMA",
      "verification_status": "PUBLISHED",
      ...
    }
  ]
}
```

### Step 5: View Alerts in Flutter App

1. Open app at http://localhost:8080
2. Go to **Alerts** tab
3. Pull down to refresh (sync with backend)
4. Alerts should appear with:
   - Source (NDMA/PDMA/PMD)
   - Timestamp
   - Verification badge

---

## Part 3: Verify Everything is Working

### Checklist

- [ ] Ollama service running (`curl http://localhost:11434/api/tags`)
- [ ] Backend `.env` has `LLM_PROVIDER=ollama`
- [ ] Backend running on port 8002
- [ ] Flutter app loads at http://localhost:8080
- [ ] Chat returns natural language answers (not raw chunks)
- [ ] Scheduler shows `"running": true` at `/monitor/status`
- [ ] Alerts tab shows fetched alerts

### Test RAG End-to-End

**Query:** "How to prepare for a flood in Chitral?"

**Expected behavior:**
1. Flutter sends POST to `/rag/query`
2. Backend searches `knowledge.sqlite` (retrieval)
3. Passes chunks to Ollama via `http://localhost:11434/v1/chat/completions`
4. Ollama rephrases answer (generation)
5. Returns JSON with `provider_used: "ollama"`, `generation_used: true`
6. Flutter displays natural answer + sources

**Before (no LLM):**
```
"Store food, water, medicine. Keep torch and charged phone. 
Source: NDMA, Flood Preparedness Guidelines, 2022"
```

**After (with Ollama):**
```
"To prepare for a flood in Chitral, ensure you have a 3-day supply 
of food and clean water. Keep essential medicines, a working torch, 
and fully charged phone with you. Monitor PDMA KP alerts regularly.

Source: NDMA, Flood Preparedness Guidelines, 2022"
```

---

## Part 4: Jury Defense Points

### "How is AI actually used?"

**Answer:**
> "Our RAG system has two layers: retrieval and generation. Retrieval is mandatory — it searches 315 verified NDMA/PDMA document chunks in our SQLite database. Generation is optional — when enabled via `LLM_PROVIDER=ollama`, it calls a local Llama 3 model running on the same machine. The model only rephrases already-retrieved text — it never invents facts. If retrieval confidence is below threshold, the system returns 'INSUFFICIENT EVIDENCE' and skips generation entirely. This is Constraint 5 in our architecture."

**Evidence:** `backend/services/rag_service.py` L85-90

### "Is this real-time?"

**Answer:**
> "Our alert ingestion runs every 6 hours via APScheduler. The scheduler calls `official_alert_monitor.py`, which scrapes NDMA's public website (no official API exists). When new alerts are detected, they go through a lifecycle: DISCOVERED → VERIFIED → PUBLISHED. The Flutter app syncs on-demand via pull-to-refresh. This is as real-time as possible given the data source constraints."

**Evidence:** `backend/core/scheduler.py` L89-95, `fetchers/official_alert_monitor.py`

### "Why Ollama instead of OpenAI?"

**Answer:**
> "Three reasons: (1) No API costs — critical for a government/NGO deployment with no budget. (2) Offline capability — Ollama runs locally, no internet needed. (3) Data privacy — no user queries sent to external servers. The architecture is provider-agnostic — we support OpenAI and Groq too via environment variables — but Ollama is the production recommendation."

**Evidence:** `backend/services/rag_service.py` L36-40 (provider dispatch table)

---

## Troubleshooting

### Ollama Not Responding
```powershell
# Windows: Restart Ollama service
Stop-Service Ollama
Start-Service Ollama

# Or reinstall:
winget uninstall Ollama.Ollama
winget install Ollama.Ollama
```

### Scheduler Not Running
Check `backend/logs/`:
```powershell
cat backend/logs/scheduler.log
```

Common issues:
- `ENV=test` → scheduler disabled
- `MONITOR_ENABLED=0` → scheduler disabled  
- Port 8002 already in use

### RAG Returns Raw Text (No Generation)
```powershell
# Check LLM_PROVIDER:
cd backend
python -c "import os; print(os.getenv('LLM_PROVIDER'))"

# Expected: ollama
# If output is "none" or empty, create .env file
```

---

## Production Recommendations

**AI Model:**
- Use Ollama with `llama3:8b` for cost-free local inference
- For cloud: switch to Groq (fastest) or OpenAI (most reliable)
- Add model evaluation metrics (BLEU, ROUGE, human eval)

**Real-Time Alerts:**
- Current: 6-hour polling (limited by NDMA website structure)
- Future: If NDMA exposes a webhook API, switch to push-based ingestion
- Add FCM (Firebase Cloud Messaging) for push notifications to app
- Add alert expiry automation (e.g., expire after 48 hours)

**Both:**
- Monitor `/monitor/status` with Prometheus + Grafana
- Set up alerting if scheduler fails
- Log all LLM calls for quality auditing
