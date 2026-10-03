# Deployment Guide

This guide deploys the Fact Knowledge Layer to:

- **Railway** — PostgreSQL, Redis, FastAPI API, Celery worker
- **Vercel** — React frontend

Total cost: **$0** on free tiers for normal usage.

---

## Prerequisites

- GitHub account (repo already pushed)
- Railway account — sign up at https://railway.app (free)
- Vercel account — sign up at https://vercel.com (free)
- Gemini API key — get one free at https://aistudio.google.com/apikey

---

## Part 1 — Railway (Backend)

### Step 1 — Create a new Railway project

1. Go to https://railway.app
2. Click **New Project**
3. Choose **Deploy from GitHub repo**
4. Select `fact-knowledge-layer-submission`

---

### Step 2 — Add PostgreSQL with pgvector

1. In your Railway project click **+ New**
2. Choose **Database → PostgreSQL**
3. Wait for it to provision (1-2 minutes)
4. Click the PostgreSQL service → **Variables** tab
5. Note the `DATABASE_URL` — Railway will inject this automatically

> **Important:** Railway's PostgreSQL has pgvector available. The migration will run `CREATE EXTENSION IF NOT EXISTS vector` automatically on first deploy.

---

### Step 3 — Add Redis

1. Click **+ New → Database → Redis**
2. Wait for it to provision
3. Note the `REDIS_URL` — Railway will inject this automatically

---

### Step 4 — Deploy the FastAPI service

1. Click **+ New → GitHub Repo → fact-knowledge-layer-submission**
2. Railway will detect the `railway.toml` and offer two services: `api` and `worker`
3. Select **api** first
4. Go to **Settings → Build** and set:
   - **Root directory:** `backend`
   - **Dockerfile path:** `Dockerfile`
5. Go to **Variables** and add:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
ENVIRONMENT=production
DEBUG=false
UPLOAD_DIR=./storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_ORIGINS=https://your-app.vercel.app
```

> Leave `DATABASE_URL` and `REDIS_URL` blank — Railway injects them automatically from the database services.

6. Click **Deploy**

---

### Step 5 — Deploy the Celery worker

1. Click **+ New → GitHub Repo → fact-knowledge-layer-submission** again
2. This time set:
   - **Root directory:** `backend`
   - **Dockerfile path:** `Dockerfile.celery`
3. Add the **same environment variables** as the API service above
4. Click **Deploy**

---

### Step 6 — Note your API URL

Once the API service is running, Railway gives you a public URL like:
```
https://fact-knowledge-layer-api-production.up.railway.app
```

Copy this — you'll need it for the frontend.

---

## Part 2 — Vercel (Frontend)

### Step 1 — Import the project

1. Go to https://vercel.com
2. Click **Add New → Project**
3. Import `fact-knowledge-layer-submission` from GitHub
4. Set:
   - **Root directory:** `frontend`
   - **Framework preset:** Vite (auto-detected)
   - **Build command:** `npm run build`
   - **Output directory:** `dist`

---

### Step 2 — Set environment variables

In Vercel project settings → **Environment Variables** add:

```
VITE_API_BASE_URL=https://your-railway-api-url.up.railway.app/api/v1
```

Replace the URL with your actual Railway API URL from Part 1 Step 6.

---

### Step 3 — Deploy

Click **Deploy**. Vercel builds and deploys automatically in ~2 minutes.

You'll get a URL like:
```
https://fact-knowledge-layer-submission.vercel.app
```

---

### Step 4 — Update CORS on Railway

Go back to Railway → API service → **Variables** and update:

```
ALLOWED_ORIGINS=https://fact-knowledge-layer-submission.vercel.app
```

Redeploy the API service (Railway redeploys automatically on variable changes).

---

## Part 3 — Verify deployment

Open your Vercel URL and check each part works:

1. **Health check** — visit `https://your-railway-url.up.railway.app/health` → should return `{"status":"ok"}`
2. **API docs** — visit `https://your-railway-url.up.railway.app/docs` → should show Swagger UI
3. **Upload a PDF** — go to the frontend Upload tab, upload a small PDF
4. **Check Celery** — watch Railway logs for the worker service → should show extraction tasks running
5. **Fact Explorer** — after processing, check facts appear

---

## Environment variables reference

### Required for production

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (auto-injected by Railway) | `postgresql://user:pass@host/db` |
| `REDIS_URL` | Redis connection string (auto-injected by Railway) | `redis://default:pass@host:6379` |
| `LLM_PROVIDER` | LLM backend to use | `gemini` |
| `GEMINI_API_KEY` | Your Gemini API key | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini model name | `gemini-3.5-flash-lite` |
| `ALLOWED_ORIGINS` | Comma-separated frontend URLs for CORS | `https://yourapp.vercel.app` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Set to `production` on Railway |
| `DEBUG` | `true` | Set to `false` on Railway |
| `UPLOAD_DIR` | `./storage/uploads` | Where uploaded PDFs are stored |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum PDF upload size |
| `API_KEY` | `` (empty) | Optional API key to protect all endpoints |

### Frontend (Vercel)

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Full Railway API URL including `/api/v1` |

---

## Troubleshooting

### "pgvector type does not exist"
The migration must run `CREATE EXTENSION IF NOT EXISTS vector`. This is already in the migration file. Make sure the Dockerfile CMD runs `alembic upgrade head` before starting uvicorn.

### "Connection refused" on API start
Railway takes ~30 seconds to provision PostgreSQL. The `pool_pre_ping=True` setting in SQLAlchemy will retry. If it keeps failing, check `DATABASE_URL` is correctly set.

### Celery worker not picking up tasks
Check that both the API and worker services have the **same** `REDIS_URL`. If Railway injected different Redis URLs, manually copy the exact same value to both.

### CORS errors in browser
Make sure `ALLOWED_ORIGINS` on Railway exactly matches your Vercel URL (no trailing slash, correct https).

### Gemini 429 rate limit during deployment test
The free tier allows 500 requests/day. Large PDFs can exhaust this. Wait until the quota resets at midnight Pacific time, or use a different Google account's API key.

---

## Cost summary

| Service | Free tier |
|---|---|
| Railway PostgreSQL | 500MB storage, 1GB RAM |
| Railway Redis | 25MB |
| Railway API service | $5 credit/month (usually enough) |
| Railway Celery worker | $5 credit/month shared |
| Vercel frontend | Unlimited static deployments |
| Gemini API | 500 requests/day free |

For light usage (a few PDFs, occasional comparison) the total cost is **$0**.
