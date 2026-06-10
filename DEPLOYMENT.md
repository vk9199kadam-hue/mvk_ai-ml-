# 🚀 AutoInsight AI — Deployment Guide

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │     Vercel (CDN)        │
                    │  Next.js Frontend       │
                    │  autoinsight.vercel.app │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   Convex Cloud (BaaS)   │
                    │  • Database (9 tables)  │
                    │  • Server Functions     │
                    │  • File Storage         │
                    │  • LLM API Integration  │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   OpenRouter API        │
                    │  • qwen/qwen3-coder:free │
                    │  • llama-4-maverick:free │
                    └─────────────────────────┘
```

**Key Point:** This is a **serverless, device-independent** architecture. The app runs 24/7 on Convex Cloud + Vercel with zero local dependencies after deployment.

---

## 📋 Prerequisites

| Requirement | Details | Cost |
|-------------|---------|------|
| **GitHub Account** | Free — [github.com](https://github.com) | $0 |
| **Vercel Account** | Free — [vercel.com](https://vercel.com) | $0 |
| **Convex Account** | Free — [convex.dev](https://convex.dev) | $0 |
| **OpenRouter Account** | Free — [openrouter.ai](https://openrouter.ai) | $0 (free models) |
| **OpenRouter Account** | Free — [openrouter.ai](https://openrouter.ai) | $0 (free models) |

**Total Monthly Cost: $0** (all platforms offer free tiers)

---

## ⚡ Quick Deploy (15 Minutes)

### Step 1: Clone & Install

```bash
# Clone the repository
git clone https://github.com/your-org/autoinsight-ai.git
cd autoinsight-ai/frontend

# Install dependencies
npm install
```

### Step 2: Get Your API Keys

#### OpenRouter API Key (Required — Primary LLM Provider)

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up (or log in)
3. Click **"Create API Key"**
4. Copy the key (starts with `sk-or-v1-`)

> **Why OpenRouter?** We use `qwen/qwen3-coder:free` and `meta-llama/llama-4-maverick:free` — both are **completely free** models.
> Rate limits apply: ~20 RPM, ~200 RPD for free models.

#### Convex Setup

1. Go to [dashboard.convex.dev](https://dashboard.convex.dev)
2. Create an account with GitHub
3. A project will be auto-created (or create one named "autoinsight-ai")
4. Note your **Deployment URL** (e.g., `https://sleek-herring-766.convex.cloud`)

### Step 3: Configure Environment

```bash
cd frontend
cp .env.example .env.local
```

Edit `.env.local`:

```env
# ── Convex ─────────────────────────────────────
NEXT_PUBLIC_CONVEX_URL=https://sleek-herring-766.convex.cloud  # ← Your Convex URL

# ── OpenRouter (Sole LLM Provider) ─────────────
OPENROUTER_API_KEY=sk-or-v1-your-key-here       # ← Your OpenRouter API key
```

### Step 4: Deploy Convex Backend

```bash
cd frontend

# Log in to Convex (opens browser for auth)
npx convex login

# Deploy all server functions to Convex Cloud
npx convex deploy
```

This deploys:
- ✅ Database schema (9 tables with indexes)
- ✅ All queries, mutations, and actions
- ✅ File storage configuration

**Verify:** Visit [dashboard.convex.dev](https://dashboard.convex.dev) → Your project → Functions tab. You should see all deployed functions listed.

### Step 5: Deploy Frontend to Vercel

#### Option A: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login and deploy
cd frontend
vercel --prod
```

When prompted:
- Set `NEXT_PUBLIC_CONVEX_URL` to your Convex deployment URL
- Set `OPENROUTER_API_KEY` to your key
- OpenRouter is the sole LLM provider (no Groq needed)

#### Option B: Deploy via GitHub + Vercel (Recommended)

1. Push your repo to GitHub:
```bash
git remote add origin https://github.com/your-org/autoinsight-ai.git
git push -u origin main
```

2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your GitHub repository
4. Select the `frontend` directory as the root
5. Add environment variables (see below)
6. Click **Deploy**

**Required Environment Variables in Vercel:**

| Variable | Value | Secret? |
|----------|-------|---------|
| `NEXT_PUBLIC_CONVEX_URL` | `https://sleek-herring-766.convex.cloud` | No |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | ✅ Yes |
| OpenRouter only | No additional API keys needed | — |
| `NEXT_PUBLIC_APP_URL` | `https://autoinsight.vercel.app` | No |

### Step 6: Verify Deployment

Open your Vercel URL (e.g., `https://autoinsight.vercel.app`). You should see:

1. ✅ Login page loads
2. ✅ You can register a new account
3. ✅ Dashboard loads with no errors
4. ✅ NLQ Chat works
5. ✅ Reports generate (requires data upload first)

---

## 🔧 CI/CD Pipeline (GitHub Actions)

The project includes a pre-configured CI/CD pipeline (`.github/workflows/ci-cd.yml`):

```yaml
jobs:
  quality:        # TypeScript + Lint checks on every push
  deploy-convex:  # Auto-deploys Convex on main branch pushes
  deploy-vercel:  # Auto-deploys Vercel on main branch pushes
```

### Setup GitHub Secrets:

In your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → Add these:

| Secret | Description | How to Get |
|--------|-------------|------------|
| `CONVEX_DEPLOY_KEY` | Convex deployment key | `npx convex deploy-key` from frontend/ |
| `VERCEL_TOKEN` | Vercel access token | [vercel.com/account/tokens](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | Vercel org ID | From Vercel project settings |
| `VERCEL_PROJECT_ID` | Vercel project ID | From Vercel project settings |

---

## 📦 Project Structure (Deployment-Ready)

```
autoinsight-ai/
├── frontend/                    ← Deploys to Vercel
│   ├── convex/                  ← Deploys to Convex Cloud
│   │   ├── schema.ts            ← 9 database tables
│   │   ├── lib/
│   │   │   ├── openrouter.ts    ← Primary LLM (3-tier fallback)
│   │   │   ├── groq.ts          ← Removed (OpenRouter-only)
│   │   │   └── export_templates.ts
│   │   ├── pipeline/            ← 4-stage pipeline
│   │   ├── reports.ts           ← 8-agent report engine
│   │   ├── nlq.ts               ← NLQ chat
│   │   ├── audit.ts             ← Enterprise audit log
│   │   └── ...                  ← 20+ server functions
│   ├── src/                     ← React/Next.js app
│   │   ├── app/                 ← 9 pages
│   │   └── components/          ← UI components
│   ├── .env.example             ← Template for env vars
│   └── package.json
├── backend/                     ← Local dev only (not deployed)
│   └── ...                      ← Python FastAPI (for reference)
├── DEPLOYMENT.md                ← This guide
└── FINAL_PROJECT_REPORT.md      ← Full documentation
```

---

## 🔐 Environment Variables Reference

### Required

| Variable | Where Used | Description |
|----------|------------|-------------|
| `NEXT_PUBLIC_CONVEX_URL` | `providers.tsx` | Convex deployment URL |
| `OPENROUTER_API_KEY` | `convex/lib/openrouter.ts` | OpenRouter API key for LLM |

### Optional

| Variable | Where Used | Description |
|----------|------------|-------------|
| `OPENROUTER_API_KEY` (sole provider) | `convex/lib/openrouter.ts` | OpenRouter API key for all LLM calls |
| `NEXT_PUBLIC_API_URL` | `src/lib/api.ts` | Backend API URL (local dev only) |
| `NEXT_PUBLIC_APP_URL` | `convex/lib/openrouter.ts` | App URL for OpenRouter referer header |

---

## 🧪 Post-Deployment Verification Checklist

- [ ] **Login/Register** works
- [ ] **Upload CSV** — can upload files to Convex Storage
- [ ] **Pipeline** — 4 stages run successfully
- [ ] **Reports** — generate with confidence gating
- [ ] **NLQ Chat** — natural language queries work
- [ ] **Dashboard** — shows charts with drill-down
- [ ] **Admin** — user management works
- [ ] **System Status** — `/system` page shows health
- [ ] **PWA** — service worker registers, offline page works
- [ ] **Audit Log** — enterprise audit log active
- [ ] **PII Masking** — auto-detected in data

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| `NEXT_PUBLIC_CONVEX_URL` not set | Run `npx convex dev --once` to get it |
| OpenRouter 401 | Verify your API key in `.env.local` or Vercel env vars |
| Convex functions not found | Run `npx convex deploy` |
| TypeScript errors about `_generated/` | Run `npx convex dev --once` to generate types |
| 504 Gateway Timeout | Add `OPENROUTER_API_KEY` env var in Vercel dashboard |
| PWA not installing | HTTPS required for PWA — Vercel provides this |

---

## 📊 Monitoring & Maintenance

- **Convex Dashboard**: [dashboard.convex.dev](https://dashboard.convex.dev) — monitor function calls, errors, database size
- **Vercel Dashboard**: [vercel.com/dashboard](https://vercel.com/dashboard) — monitor deployments, serverless function logs
- **OpenRouter Dashboard**: [openrouter.ai/activity](https://openrouter.ai/activity) — monitor API usage and costs

---

## 🔮 Next Steps After Deployment

1. **Add custom domain** in Vercel → Project → Domains
2. **Set up monitoring** — Convex dashboard is pre-configured
3. **Add auth providers** — Update `convex/auth.config.ts` for GitHub/Google OAuth
4. **Scale up** — Convex auto-scales; Vercel Pro removes function timeout limits
