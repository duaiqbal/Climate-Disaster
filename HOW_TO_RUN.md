# ChitralSafe - How to Run

## 🚀 **ONE-CLICK STARTUP (EASIEST)**

**Double-click this file:**
```
START_CHITRALSAFE.bat
```

✅ **Automatically starts:**
- Backend API (port 8002)
- Flutter Web App (port 8080)
- Opens Chrome automatically

---

## 🌐 **OPEN IN BROWSER ANYTIME**

**Double-click this file:**
```
OPEN_IN_BROWSER.bat
```

✅ **Opens app in Chrome** (starts services if needed)

---

## ⏹️ **STOP ALL SERVICES**

**Double-click this file:**
```
STOP_CHITRALSAFE.bat
```

✅ **Stops backend and Flutter**

---

## 🔧 **MANUAL STARTUP (If Batch Files Fail)**

### **Option 1: Two Terminals**

**Terminal 1 - Backend:**
```powershell
cd backend
python -m uvicorn main:app --port 8002
```

**Terminal 2 - Flutter:**
```powershell
cd app
flutter run -d chrome --web-port 8080
```

### **Option 2: PowerShell Scripts**

**Terminal 1:**
```powershell
cd backend
.\start_backend.ps1
```

**Terminal 2:**
```powershell
cd app
.\run_web.ps1
```

---

## 🎯 **ACCESS POINTS**

| Service | URL | Purpose |
|---------|-----|---------|
| **App** | http://localhost:8080 | Main application |
| **API** | http://localhost:8002 | Backend API |
| **Docs** | http://localhost:8002/docs | API documentation |
| **Health** | http://localhost:8002/health | Backend status |

---

## ✅ **VERIFY IT'S RUNNING**

```powershell
# Check backend
curl http://localhost:8002/health

# Check Flutter
curl http://localhost:8080
```

Both should respond without errors.

---

## 🐛 **TROUBLESHOOTING**

### **Problem: Port already in use**

```powershell
# Kill existing processes
taskkill /F /IM python.exe
taskkill /F /IM dart.exe
```

### **Problem: Backend not responding**

```powershell
cd backend
python -m uvicorn main:app --port 8002 --reload
```

### **Problem: Flutter won't compile**

```powershell
cd app
flutter clean
flutter pub get
flutter run -d chrome --web-port 8080
```

---

## 📱 **FEATURES TO TEST**

1. **Dashboard:** Personalized greeting, risk indicator
2. **Chat:** Type "What to do in flood?" (responds in 3s)
3. **Alerts:** Pull to refresh, real data
4. **Safety:** Go Bag checklist
5. **Profile:** Emergency contacts (1122)

---

## 🎓 **FOR DEFENSE PANEL**

- **Chatbot timeout:** 3 seconds (instant feedback)
- **Offline capability:** SQLite on mobile, demo on web
- **Real-time alerts:** 6-hour refresh cycle
- **Security:** bcrypt password hashing (12 rounds)
- **AI Integration:** Ollama/Llama3 RAG system

**Show them:** Backend logs, API docs, chatbot response time

---

## 📦 **PROJECT STRUCTURE**

```
disaster_dss/
├── START_CHITRALSAFE.bat    ← Main launcher
├── OPEN_IN_BROWSER.bat      ← Quick browser open
├── STOP_CHITRALSAFE.bat     ← Stop all services
├── backend/                  ← FastAPI backend
│   ├── start_backend.ps1    ← Backend launcher
│   └── main.py              ← API entry point
└── app/                      ← Flutter app
    ├── run_web.ps1          ← Flutter web launcher
    └── lib/                  ← App source code
```

---

**Created by: ChitralSafe Team**  
**Last Updated: 2026-09-12**
