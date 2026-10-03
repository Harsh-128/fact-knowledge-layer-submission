# Deployment Guide — Fully Free Stack

Deploy the Fact Knowledge Layer for **$0** with no expiry using:

| Service | Platform | Free limits |
|---|---|---|
| PostgreSQL + pgvector | **Supabase** | 500 MB, never expires |
| Redis (Celery broker) | **Upstash** | 500K commands/month, never expires |
| FastAPI API | **Render** | 750 hrs/month, free forever |
| Celery worker | **Render** | Free background worker |
| React frontend | **Vercel** | Unlimited, free forever |
| LLM inference | **Gemini API** | 500 req/day free, no credit card |

**Total cost: $0 — works for 3–4 months and beyond.**

> ⚠️ One limitation: Render free web services **sleep after 15 minutes of inactivity**. The first request after idle takes ~30 seconds to wake up. This is fine for a demo or portfolio app.

---

## Overview — what you'll do

```
Step 1  →  Supabase   (PostgreSQL + pgvector database)
Step 2  →  Upstash    (Redis for Celery)
Step 3  →  Render     (FastAPI API + Celery worker)
Step 4  →  Vercel     (React frontend)
Step 5  →  Wire it up (set env vars, CORS)
```

---

## Prerequisites

- GitHub account (repo already pushed ✅)
- Gemini API key — get free at https://aistudio.google.com/apikey
- Supabase account — sign up at https://supabase.com (free, no card)
- Upstash account — sign up at https://upstash.com (free, no card)
- Render account — sign up at https://render.com (free, no card)
- Vercel account — sign up at https://vercel.com (free, no card)

---

## Part 1 — Supabase (PostgreSQL + pgvector)

### 1.1 Create a project

1. Go to https://supabase.com → **New project**
2. Choose a name: `fact-knowledge-layer`
3. Set a strong database password — **save it**, you'll need it
4. Choose the **free** plan
5. Pick the region closest to you
6. Click **Create new project** (takes ~2 minutes)

### 1.2 Enable pgvector

1. In your Supabase project go to **SQL Editor**
2. Run this query:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. Click **Run** — you should see `Success`

### 1.3 Get the connection string

1. Go to **Project Settings → Database**
2. Scroll to **Connection string → URI**
3. Select **Transaction pooler** mode (port 6543)
4. Copy the URI — it looks like:

```
postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

5. **Replace `[YOUR-PASSWORD]` with your actual password**
6. Save this — it's your `DATABASE_URL`

---

## Part 2 — Upstash (Redis)

### 2.1 Create a Redis database

1. Go to https://console.upstash.com → **Create database**
2. Name: `fact-layer-redis`
3. Type: **Regional** (not Global — simpler and free)
4. Region: pick one close to your Render region
5. Click **Create**

### 2.2 Get the connection URL

1. Click your database → **Details** tab
2. Copy **REDIS_URL** — it looks like:

```
rediss://default:YOUR_PASSWORD@your-host.upstash.io:6380
```

Save this — it's your `REDIS_URL`.

---

## Part 3 — Render (FastAPI + Celery)

### 3.1 Deploy the API service

1. Go to https://render.com → **New + → Web Service**
2. Connect your GitHub account and select `fact-knowledge-layer-submission`
3. Configure:
   - **Name:** `fact-knowledge-layer-api`
   - **Root directory:** `backend`
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Plan:** Free

4. Click **Advanced** → add these **Environment Variables**:

| Key | Value |
|---|---|
| `DATABASE_URL` | Your Supabase connection string |
| `REDIS_URL` | Your Upstash Redis URL |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `UPLOAD_DIR` | `./storage/uploads` |
| `MAX_UPLOAD_SIZE_MB` | `50` |
| `ALLOWED_ORIGINS` | *(leave blank for now — fill in after Vercel deploy)* |

5. Click **Create Web Service**
6. Wait for the build (~5 minutes) — watch the logs
7. Note your API URL: `https://fact-knowledge-layer-api.onrender.com`

> The first deploy runs `alembic upgrade head` automatically, creating all tables.

### 3.2 Deploy the Celery worker

1. Go to **New + → Background Worker**
2. Same repo: `fact-knowledge-layer-submission`
3. Configure:
   - **Name:** `fact-knowledge-layer-worker`
   - **Root directory:** `backend`
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile.celery`
   - **Plan:** Free

4. Add the **same environment variables** as the API service above (DATABASE_URL, REDIS_URL, GEMINI_API_KEY, etc.)
5. Click **Create Background Worker**
6. Wait for the build — you should see `celery@hostname ready` in the logs

---

## Part 4 — Vercel (Frontend)

### 4.1 Import the project

1. Go to https://vercel.com → **Add New → Project**
2. Import `fact-knowledge-layer-submission` from GitHub
3. Configure:
   - **Root directory:** `frontend`
   - **Framework preset:** Vite *(auto-detected)*
   - **Build command:** `npm run build`
   - **Output directory:** `dist`

### 4.2 Add environment variable

Under **Environment Variables** add:

| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://fact-knowledge-layer-api.onrender.com/api/v1` |

*(Replace with your actual Render API URL)*

### 4.3 Deploy

Click **Deploy** — Vercel builds in ~2 minutes.

You'll get a URL like:
```
https://fact-knowledge-layer-submission.vercel.app
```

---

## Part 5 — Wire everything together

### 5.1 Update CORS on Render

Go back to your Render **API service → Environment** and update:

| Key | Value |
|---|---|
| `ALLOWED_ORIGINS` | `https://fact-knowledge-layer-submission.vercel.app` |

Render redeploys automatically after saving.

### 5.2 Verify everything works

1. **Health check** — open:
   ```
   https://fact-knowledge-layer-api.onrender.com/health
   ```
   Should return: `{"status":"ok","service":"Fact Knowledge Layer",...}`

2. **API docs** — open:
   ```
   https://fact-knowledge-layer-api.onrender.com/docs
   ```
   Should show the Swagger UI with all endpoints.

3. **Frontend** — open your Vercel URL and upload a small PDF.

4. **Worker logs** — check Render → Background Worker logs for:
   ```
   celery@hostname ready.
   ```

5. **After upload** — check the worker logs for extraction tasks running.

---

## Environment variables reference

### Render API + Worker services

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL connection string |
| `REDIS_URL` | ✅ | Upstash Redis connection URL |
| `LLM_PROVIDER` | ✅ | `gemini` |
| `GEMINI_API_KEY` | ✅ | Your Gemini API key |
| `GEMINI_MODEL` | ✅ | `gemini-3.5-flash-lite` |
| `ALLOWED_ORIGINS` | ✅ | Your Vercel frontend URL |
| `ENVIRONMENT` | ✅ | `production` |
| `DEBUG` | ✅ | `false` |
| `UPLOAD_DIR` | optional | `./storage/uploads` |
| `MAX_UPLOAD_SIZE_MB` | optional | `50` |
| `API_KEY` | optional | Set to protect all endpoints with a key |

### Vercel frontend

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | ✅ | Full Render API URL + `/api/v1` |

---

## Troubleshooting

### Build fails on Render: "mupdf not found"
The Dockerfile installs `libmupdf-dev`. If Render can't find it, make sure the **Dockerfile path** is set to `./Dockerfile` and **Root directory** is `backend`.

### "pgvector type does not exist"
You need to run `CREATE EXTENSION IF NOT EXISTS vector;` in Supabase SQL Editor first (Part 1.2 above).

### API returns 500 on first request after deploy
The migration may not have run yet. Check Render API logs for `alembic upgrade head`. If it failed, re-deploy the API service.

### CORS error in browser console
Make sure `ALLOWED_ORIGINS` on Render exactly matches your Vercel URL — no trailing slash, must be `https://`.

### Celery worker not processing tasks
Make sure both the API and worker have the **exact same** `REDIS_URL`. If they differ, tasks get queued on one broker and the worker listens on another.

### Supabase "project paused" after 7 days
Supabase pauses free projects after 7 days with no activity. Just visit your Supabase dashboard and click **Restore project** — takes 30 seconds. To avoid this, make sure you use the app at least once a week, or set up a free cron job at https://cron-job.org to ping `https://your-api.onrender.com/health` every 6 days.

### Render API cold start takes 30 seconds
This is normal for the free tier. The service sleeps after 15 minutes of no traffic. To reduce this, use the same cron-job.org trick — ping the `/health` endpoint every 14 minutes to keep it awake.

**Free keep-alive setup:**
1. Go to https://cron-job.org → sign up free
2. Create a cron job:
   - URL: `https://your-api.onrender.com/health`
   - Schedule: every 14 minutes
3. This keeps your API awake 24/7 for free

---

## Free tier limits summary

| Platform | What's free | What happens when exceeded |
|---|---|---|
| Supabase | 500 MB storage, 2 projects | Project pauses (not deleted) |
| Upstash | 500K Redis commands/month | Requests blocked until next month |
| Render API | 750 hrs/month | Service suspended until next month |
| Render Worker | 750 hrs/month | Worker suspended until next month |
| Vercel | Unlimited static deployments | Never exceeded for this app |
| Gemini API | 500 req/day per key | 429 errors until midnight Pacific |

For a demo/portfolio app with occasional use, **none of these limits will be hit**.
