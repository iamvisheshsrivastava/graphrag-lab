# Deployment Guide

## Stack

| Part | Host | Free tier | Notes |
|---|---|---|---|
| Frontend (React/Vite) | **Vercel** | ✅ | CDN, auto-deploy from GitHub |
| Backend (FastAPI) | **Render** | ✅ | Persistent process, keeps graph in memory |

> Vercel alone doesn't work for the backend — it's serverless (stateless), so the in-memory graph resets between requests.

---

## Step 1 — Deploy Backend on Render

1. Go to [render.com](https://render.com) and sign up (free)
2. **New → Web Service → Connect GitHub repo** → select `graphrag-lab`
3. Settings:
   - **Root directory:** `backend`
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment Variables**, add:
   - `OPENROUTER_API_KEY` = your key
5. Click **Deploy**
6. Once live, copy the URL — it looks like `https://graphrag-lab-api.onrender.com`

> The `render.yaml` in the repo root pre-fills all settings automatically.

---

## Step 2 — Deploy Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) and sign up (free)
2. **Add New Project → Import Git Repository** → select `graphrag-lab`
3. Settings:
   - **Root directory:** `frontend`
   - **Framework preset:** Vite
   - **Build command:** `npm run build`
   - **Output directory:** `dist`
4. Under **Environment Variables**, add:
   - `VITE_API_URL` = your Render backend URL (e.g. `https://graphrag-lab-api.onrender.com`)
5. Update `frontend/vercel.json` — replace the destination URL with your actual Render URL:
   ```json
   { "source": "/api/(.*)", "destination": "https://YOUR-RENDER-URL.onrender.com/$1" }
   ```
6. Click **Deploy**

---

## Step 3 — Share the link

After Vercel deploys, you get a URL like:
```
https://graphrag-lab.vercel.app
```

Share this — anyone can open it without installing anything.

---

## Notes

- **Render free tier** spins down after 15 min of inactivity. First request after sleep takes ~30s to wake up. Upgrade to Render Starter ($7/mo) for always-on.
- The in-memory graph resets when the Render process restarts. For persistent state, add Neo4j AuraDB (free tier available).
- Both services auto-redeploy when you push to `main` on GitHub.
