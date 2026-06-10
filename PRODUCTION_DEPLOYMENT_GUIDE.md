# 🚀 AutoInsight AI — Production Deployment Guide

> **Complete Step-by-Step Guide — Go Live in ~30 Minutes**
> 
> This guide covers the **4 remaining steps** to take AutoInsight AI from local development to **production**.

---

## 📋 Prerequisites Check

Before starting, confirm you have these accounts:

| Account | Status | Sign-Up Link |
|---------|--------|-------------|
| **GitHub** | ⬜ | [github.com](https://github.com) |
| **Convex** | ✅ Already configured | Project: `sleek-herring-766` |
| **Vercel** | ⬜ | [vercel.com](https://vercel.com) |
| **OpenRouter** | ⬜ | [openrouter.ai](https://openrouter.ai) |

**OpenRouter is the sole LLM provider.** The platform uses a 2-tier fallback:
- **Primary:** `qwen/qwen3-coder:free` (OpenRouter)
- **Fallback:** `meta-llama/llama-4-maverick:free` (OpenRouter)

Both models are **completely free**. No other API keys are needed.

---

## 🔴 CRITICAL — Current Status

| Item | Current State | Action Needed |
|------|-------------|--------------|
| **Git Repository** | ❌ NOT initialized | Initialize git + push to GitHub |
| **API Key (.env.local)** | ❌ Missing OpenRouter key | Add OpenRouter API key |
| **Convex Deployment** | ⚠️ Local dev only | Deploy to Convex Cloud |
| **Vercel Deployment** | ❌ Not deployed | Deploy frontend |
| **CI/CD Automation** | ❌ Not configured | Set GitHub Secrets |

---

# STEP 1: 🔑 Get OpenRouter API Key & Configure .env.local

## 1.1 — Get Your OpenRouter API Key (Required)

OpenRouter is your **sole LLM provider**. Without it, AI features (pipeline, reports, NLQ chat) won't work.

**Steps:**
1. Go to **[openrouter.ai/keys](https://openrouter.ai/keys)**
2. Click **Sign Up** (or log in if you already have an account)
3. Click **"Create API Key"**
4. Name it: `AutoInsight AI`
5. **Copy the key** — it starts with `sk-or-v1-`
6. Store it somewhere safe (you'll need it multiple times)

> ⚠️ **Keep this key private!** Anyone with this key can use your OpenRouter account.

## 1.2 — Update .env.local with Production Values

Now update your `.env.local` file. Currently it has local-only Convex dev URLs.

Open the file at `autoinsight-ai/frontend/.env.local` and replace with:

```env
# ── Convex (Required) ─────────────────────────────────────────────────────
# Production Convex URL — already configured in convex.json
NEXT_PUBLIC_CONVEX_URL=https://sleek-herring-766.convex.cloud

# ── OpenRouter API Key (Required for LLM) ─────────────────────────────────
# PASTE YOUR OPENROUTER API KEY HERE
OPENROUTER_API_KEY=sk-or-v1-YOUR-ACTUAL-KEY-HERE

# ── App URL (Set to your Vercel URL after deployment) ─────────────────────
# For now use localhost, update after Vercel deployment
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

> 🔴 **Important:** Replace `sk-or-v1-YOUR-ACTUAL-KEY-HERE` with your actual OpenRouter key.

---

# STEP 2: 🚀 Initialize Git + Deploy to Convex Cloud

## 2.1 — Initialize Git Repository

```bash
cd autoinsight-ai
git init
git add .
git commit -m "Initial commit — AutoInsight AI v1.0.0"
git branch -M main
```

## 2.2 — Create GitHub Repository

1. Go to **[github.com/new](https://github.com/new)**
2. **Repository name:** `autoinsight-ai`
3. **Visibility:** `Private` or `Public`
4. Click **"Create repository"**

## 2.3 — Push to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/autoinsight-ai.git
git push -u origin main
```

## 2.4 — Install Dependencies & Deploy Convex

```bash
cd autoinsight-ai/frontend
npm install
npx convex login
npx convex deploy
```

**What gets deployed:**
- ✅ Database schema (9 tables with indexes)
- ✅ All 20+ server functions (queries, mutations, actions)
- ✅ File storage configuration

---

# STEP 3: 🌐 Deploy Frontend to Vercel

## 3.1 — Create Vercel Account

1. Go to **[vercel.com](https://vercel.com)**
2. Sign up with GitHub

## 3.2 — Deploy via Vercel CLI

```bash
cd autoinsight-ai/frontend
vercel login
vercel --prod
```

**Add environment variables when prompted:**

| Variable | Value | Secret? |
|----------|-------|---------|
| `NEXT_PUBLIC_CONVEX_URL` | `https://sleek-herring-766.convex.cloud` | No |
| `OPENROUTER_API_KEY` | `sk-or-v1-YOUR-ACTUAL-KEY` | ✅ Yes |
| `NEXT_PUBLIC_APP_URL` | `https://autoinsight-ai.vercel.app` | No |

---

# STEP 4: 🔐 Set Up CI/CD Pipeline with GitHub Secrets

## 4.1 — Generate Convex Deploy Key

```bash
cd autoinsight-ai/frontend
npx convex deploy-key
# Copy the output key
```

## 4.2 — Get Vercel Details

- **Vercel Token:** [vercel.com/account/tokens](https://vercel.com/account/tokens) → Create
- **Vercel Org ID & Project ID:** Vercel → Project → Settings → General

## 4.3 — Add Secrets to GitHub

In GitHub repo → **Settings** → **Secrets and variables** → **Actions** → Add:

| Secret | Source |
|--------|--------|
| `CONVEX_DEPLOY_KEY` | From `npx convex deploy-key` |
| `VERCEL_TOKEN` | From [vercel.com/account/tokens](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | Vercel project settings |
| `VERCEL_PROJECT_ID` | Vercel project settings |

---

## 🧪 Post-Deployment Verification

| # | Test | Expected |
|---|------|----------|
| 1 | Open `https://autoinsight-ai.vercel.app` | Login page loads |
| 2 | Register a new account | Redirects to Dashboard |
| 3 | Upload a sample CSV file | Pipeline runs successfully |
| 4 | View Reports | 8-section report loads |
| 5 | Try NLQ Chat | AI responds with analysis |
| 6 | Check Dashboard | Charts render with drill-down |
| 7 | Export HTML/MD/PDF/Excel | Files download correctly |
| 8 | Go to `/system` | Shows OpenRouter + healthy status |

---

## 📊 Key URLs Reference

| Resource | URL |
|----------|-----|
| **Live App** | `https://autoinsight-ai.vercel.app` |
| **Convex Dashboard** | `https://dashboard.convex.dev` |
| **Vercel Dashboard** | `https://vercel.com/dashboard` |
| **OpenRouter Activity** | `https://openrouter.ai/activity` |
| **GitHub Repository** | `https://github.com/YOUR_USERNAME/autoinsight-ai` |

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| OpenRouter 401 | Verify OPENROUTER_API_KEY in Vercel env vars |
| Convex functions not found | Run `npx convex deploy` |
| Vercel build fails | Run `npm run build` locally first to debug |
| Pipeline too slow | Normal for free models; upgrade to paid for faster speeds |

---

*AutoInsight AI v1.0.0 — OpenRouter Only — June 2026*
