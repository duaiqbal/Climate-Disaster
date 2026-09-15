# 🚀 ChitralSafe — Deployment Guide

Complete guide to deploy ChitralSafe online so anyone in the world can access it.

---

## 📋 Options

| Option | Cost | URL | Best For |
|--------|------|-----|----------|
| **Render.com** ✅ | Free | `https://chitral-safe-backend.onrender.com` | FYP Demo |
| Railway.app | Free tier | Custom URL | Team sharing |
| VPS (DigitalOcean) | ~$6/month | Custom domain | Production |

---

## ✅ Option 1 — Render.com (FREE — Recommended)

Render gives you:
- Free backend hosting (FastAPI)
- Free static site hosting (Flutter Web)
- Auto-deploy from GitHub — push code = auto redeploy
- HTTPS included (no setup needed)
- Public URL accessible from anywhere

### Step 1 — Create Render Account

Go to: **https://render.com**
- Click **"Get Started for Free"**
- Sign up with **GitHub** account (same account as your repo)

### Step 2 — Deploy Backend (FastAPI)

1. Go to **https://dashboard.render.com**
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"** → select **`duaiqbal/Climate-Disaster`**
4. Fill in settings:

| Field | Value |
|-------|-------|
| Name | `chitral-safe-backend` |
| Region | Singapore (closest to Pakistan) |
| Branch | `master` |
| Root Directory | `backend` |
| Runtime | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Plan | **Free** |

5. Scroll down to **"Environment Variables"** — add these:

| Key | Value |
|-----|-------|
| `ENV` | `production` |
| `SECRET_KEY` | Click **"Generate"** button |
| `ADMIN_API_KEY` | Click **"Generate"** button |
| `DATABASE_URL` | `sqlite+aiosqlite:///./disaster_dss.sqlite` |
| `LLM_PROVIDER` | `none` |
| `MONITOR_ENABLED` | `1` |
| `CORS_ORIGINS` | `https://chitral-safe-app.onrender.com` |

6. Click **"Create Web Service"**
7. Wait 3-5 minutes for build to finish
8. ✅ Your backend URL: `https://chitral-safe-backend.onrender.com`

**Test it:** Open `https://chitral-safe-backend.onrender.com/health`
Should show: `{"status":"ok","version":"2.0.0"}`

---

### Step 3 — Deploy Flutter Web App

1. Click **"New +"** → **"Static Site"**
2. Connect same repository **`duaiqbal/Climate-Disaster`**
3. Fill in settings:

| Field | Value |
|-------|-------|
| Name | `chitral-safe-app` |
| Branch | `master` |
| Root Directory | *(leave empty)* |
| Build Command | (see below) |
| Publish Directory | `app/build/web` |

**Build Command** (copy exactly):
```
cd app && flutter pub get && flutter build web --release --dart-define=BACKEND_URL=https://chitral-safe-backend.onrender.com --no-web-resources-cdn
```

> ⚠️ Render's free tier doesn't have Flutter pre-installed.
> Use the **GitHub Actions** method below for Flutter web (easier).

4. Click **"Create Static Site"**

---

### Step 4 — Auto-Deploy Flutter Web via GitHub Actions (Easier)

Instead of building on Render, build Flutter locally and push to GitHub Pages:

#### 4a — Enable GitHub Pages

1. Go to your repo: `https://github.com/duaiqbal/Climate-Disaster`
2. **Settings** → **Pages**
3. Source: **GitHub Actions**

#### 4b — Create GitHub Actions workflow
The workflow file is already in the repo at `.github/workflows/deploy.yml`
(created below). It auto-builds Flutter and deploys to GitHub Pages.

**Your app URL:** `https://duaiqbal.github.io/Climate-Disaster`

---

## ✅ Option 2 — GitHub Pages (Flutter Web) + Render (Backend)

This is the **easiest combination**:
- Backend → Render.com (free)
- Flutter Web → GitHub Pages (free, auto from GitHub)

### Setup GitHub Actions for Flutter Web

Create file: `.github/workflows/deploy.yml`
```yaml
name: Deploy Flutter Web to GitHub Pages

on:
  push:
    branches: [ master ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.24.3'
          channel: 'stable'

      - name: Install dependencies
        run: cd app && flutter pub get

      - name: Build web
        run: |
          cd app
          flutter build web --release \
            --dart-define=BACKEND_URL=https://chitral-safe-backend.onrender.com \
            --no-web-resources-cdn \
            --base-href="/Climate-Disaster/"

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: app/build/web
```

After pushing this file:
- Every push to `master` → auto builds and deploys Flutter web
- **App URL:** `https://duaiqbal.github.io/Climate-Disaster`

---

## 🔑 After Deployment — Get Admin Key

After backend deploys on Render, you need the admin key to manage alerts:

1. Go to Render dashboard → your backend service
2. **Environment** tab → find `ADMIN_API_KEY` value
3. Copy it — use this for:
   - Creating alerts: `X-Admin-Key: <your-key>`
   - Triggering scraper: POST `/monitor/run`
   - Publishing knowledge: POST `/sync/publish`

---

## 🌐 Final URLs

After deployment:

| Service | URL |
|---------|-----|
| Flutter App | `https://duaiqbal.github.io/Climate-Disaster` |
| Backend API | `https://chitral-safe-backend.onrender.com` |
| API Docs | `https://chitral-safe-backend.onrender.com/docs` |
| Health Check | `https://chitral-safe-backend.onrender.com/health` |

---

## ⚠️ Render Free Tier Limitations

| Limitation | Details |
|------------|---------|
| Sleep after inactivity | Free services sleep after 15 min of no traffic |
| First request slow | ~30 seconds to wake up (cold start) |
| No persistent disk | SQLite data resets on redeploy |
| 750 hours/month | Enough for 1 service running 24/7 |

**Fix for cold start:** Share the health URL with your supervisor before demo:
`https://chitral-safe-backend.onrender.com/health`
Open it 2 minutes before demo to wake the server.

**Fix for SQLite reset:** For production, use PostgreSQL (Render provides free PostgreSQL too). But for FYP demo, SQLite is fine.

---

## 📱 Android APK with Production Backend

Once backend is deployed, build APK with production URL:

```powershell
cd app
flutter build apk --release `
  --dart-define=BACKEND_URL=https://chitral-safe-backend.onrender.com
```

APK location: `app\build\app\outputs\flutter-apk\app-release.apk`

Share this APK via WhatsApp/Google Drive — anyone can install it!

---

## 🔄 Update Deployed App

Just push to GitHub:
```bash
git add .
git commit -m "feat: your update"
git push origin master
```

Render auto-detects the push and redeploys in ~3 minutes.
GitHub Actions auto-rebuilds Flutter web in ~5 minutes.

---

## 🆘 Troubleshooting

### Backend not starting on Render
- Check **Logs** tab in Render dashboard
- Common issue: missing dependency → add to `requirements.txt`

### CORS error on deployed app
- Add your GitHub Pages URL to `CORS_ORIGINS` env var on Render
- Format: `https://duaiqbal.github.io`

### App shows "Backend unreachable"
- Backend might be sleeping (free tier)
- Open `https://chitral-safe-backend.onrender.com/health` to wake it
- App still works offline — chatbot uses local fallback

### SQLite data lost after redeploy
- This is expected on free tier
- Upgrade to Render PostgreSQL (free 90 days) for persistence
