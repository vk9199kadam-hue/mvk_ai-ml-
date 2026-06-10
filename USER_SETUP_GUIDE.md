# AutoInsight AI — User Setup & Configuration Guide

This guide details all the actions, configuration files, and command executions needed from **your side** to run AutoInsight AI locally and deploy it to production.

---

## 🔑 1. Environment Variable Files (Your Side)

### File 1: Frontend Local Config
Create a file named `.env.local` inside the `frontend/` folder:
```bash
# Location: frontend/.env.local

# ── Convex URL (Set this to your live Convex URL when deploying) ───────────
NEXT_PUBLIC_CONVEX_URL=https://sleek-herring-766.convex.cloud

# ── Convex Auth OAuth IDs (Optional — Required for V5 Google/GitHub SSO) ──
# Get Google Client ID from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Get GitHub Client ID from: https://github.com/settings/developers
GITHUB_CLIENT_ID=your-github-client-id
```

### File 2: Backend Config (Local Python Dev Only)
Create a file named `.env` inside the `backend/` folder:
```bash
# Location: backend/.env

# ── Database & Redis Setup ────────────────────────────────────────────────
DATABASE_URL=postgresql://autoinsight:changeme@localhost:5432/autoinsight
REDIS_URL=redis://localhost:6379/0

# ── Storage (MinIO) ──────────────────────────────────────────────────────
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=autoinsight-files

# ── LLM Configuration ─────────────────────────────────────────────────────
OPENROUTER_API_KEY=your-openrouter-api-key-here
JWT_SECRET=your-secure-random-string-at-least-32-chars
```

---

## ⚡ 2. Convex Dashboard Environment Variables (Your Side)
You must set your **OpenRouter API Key** in your Convex cloud environment so the serverless AI actions can execute:

### Option A: Via Convex Dashboard
1. Go to [dashboard.convex.dev](https://dashboard.convex.dev).
2. Select your project: **autoinsight-ai** (production deployment: `sleek-herring-766`).
3. Navigate to **Settings** ➡️ **Environment Variables**.
4. Click **Add Variable** and enter:
   - **Name**: `OPENROUTER_API_KEY`
   - **Value**: `your-openrouter-api-key-here`

### Option B: Via Command Line
Run the following command inside the `frontend/` directory:
```bash
npx convex env set OPENROUTER_API_KEY your-openrouter-api-key-here
```

---

## 💻 3. Local Development Commands (Your Side)

To run the Next.js app locally alongside a local Convex backend:

```bash
# 1. Install all frontend dependencies
cd frontend
npm install

# 2. Start the local Convex development server (watches and runs databases locally)
npx convex dev

# 3. Start the Next.js dev server (in a separate terminal)
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🚀 4. Production Cloud Deployment Commands (Your Side)

### Step 1: Deploy Backend Functions to Convex
Build and publish your serverless database schemas and actions to the Convex cloud:
```bash
cd frontend
npx convex deploy
```

### Step 2: Deploy Frontend to Vercel
1. Log in to [Vercel](https://vercel.com).
2. Connect your GitHub repository: **autoinsight-ai**.
3. Set the **Root Directory** to `frontend/`.
4. Add the environment variable:
   - **Name**: `NEXT_PUBLIC_CONVEX_URL`
   - **Value**: `https://sleek-herring-766.convex.cloud`
5. Click **Deploy**.
