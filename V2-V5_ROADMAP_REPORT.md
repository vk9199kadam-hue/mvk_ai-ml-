# 🗺️ AutoInsight AI — V2 to V5 Complete Roadmap & Implementation Report

> **Comprehensive technical report covering all future features, architecture requirements, device-independent platform design, and recommended open-source GitHub repositories to fulfill every need.**

---

## 📋 Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [V2: Custom Charts + Email Reports](#2-v2-custom-drag-and-drop-chart-builder--email-report-scheduling)
3. [V3: Advanced ML Integration](#3-v3-advanced-ml-integration-shap--automated-model-selection)
4. [V4: Multi-Dataset Joins](#4-v4-multi-dataset-joins--cross-dataset-relationships)
5. [V5: Enterprise SSO + NL Report Editing](#5-v5-enterprise-sso--natural-language-report-editing)
6. [Device-Independent Architecture Requirements](#6-device-independent-platform-architecture)
7. [GitHub Repository Recommendations](#7-github-repository-recommendations-master-list)
8. [Implementation Timeline & Priority](#8-implementation-timeline--priority)

---

## 1. Executive Summary

AutoInsight AI v1.0 is **100% complete** with:
- 9 database tables, 9 frontend pages, 4-stage pipeline, 8-agent report engine
- OpenRouter-only LLM (2-tier fallback: qwen/qwen3-coder:free → llama-4-maverick:free)
- 4 export formats, PII masking, audit log, PWA, CI/CD
- **$0/month operating cost**

**V2-V5 adds enterprise capabilities** to make it a full SaaS platform.

---

## 2. V2: Custom Drag-and-Drop Chart Builder + Email Report Scheduling

### 2.1 What Needs to Be Built

| Component | Description | Priority |
|-----------|-------------|----------|
| **Drag-and-Drop Chart Builder** | Users can drag chart widgets onto a grid, resize them, choose data columns, and customize visualization type (bar, line, pie, scatter, heatmap) | 🔴 High |
| **Email Report Scheduling** | Users can schedule automated email delivery of reports at set intervals (daily, weekly, monthly) | 🟡 Medium |
| **Dashboard Persistence** | Save custom dashboard layouts per user, load them on login | 🔴 High |

### 2.2 Architecture for Device Independence

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEVICE-INDEPENDENT ARCHITECTURE                │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────────────┐        │
│  │  Drag-Drop Layer     │    │  Chart Rendering Layer    │        │
│  │  react-grid-layout   │    │  recharts / plotly.js     │        │
│  │  + dnd-kit           │    │  (Responsive SVG/Canvas)  │        │
│  └──────────┬──────────┘    └──────────┬───────────────┘        │
│             │                          │                         │
│             └──────────┬──────────────┘                         │
│                        │                                         │
│               ┌────────▼────────┐                                │
│               │  Layout Store    │                                │
│               │  (Zustand/DB)   │                                │
│               │  Synced across   │                                │
│               │  all devices     │                                │
│               └────────┬────────┘                                │
│                        │                                         │
│               ┌────────▼────────┐                                │
│               │  Convex DB      │                                │
│               │  dashboards table│                               │
│               │  (layout JSON)  │                                │
│               └─────────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Key Design Decisions for Device Independence

| Requirement | Solution | Why |
|-------------|----------|-----|
| Responsive grid | `react-grid-layout` with `responsive` prop | Auto-adjusts columns based on screen width |
| Touch support | `react-grid-layout` has built-in touch events | Works on tablets and phones |
| Chart rendering | `recharts` (SVG-based) or `plotly.js` | SVGs scale perfectly on any display |
| Layout persistence | Save to Convex `dashboards` table | Layouts sync across phone/tablet/desktop |
| Dark mode | Already supported via Tailwind CSS | Consistent on all devices |

### 2.4 Implementation Plan

```
Week 1: Install dependencies & build grid
  ├── npm install react-grid-layout recharts
  ├── Create ChartPalette component (sidebar with available chart types)
  ├── Create DashboardCanvas component (grid where charts are placed)
  └── Save/load layout from Convex dashboards table

Week 2: Email scheduling
  ├── Install resend or nodemailer
  ├── Create ScheduleReport UI (cron-style selector: daily/weekly/monthly)
  ├── Create Convex mutation: scheduleReport
  └── Create Convex action: sendScheduledReport
```

---

## 3. V3: Advanced ML Integration (SHAP + Automated Model Selection)

### 3.1 What Needs to Be Built

| Component | Description | Complexity |
|-----------|-------------|------------|
| **Python ML Microservice** | Separate FastAPI server that runs scikit-learn, SHAP, XGBoost | 🔴 High |
| **Automated Model Selection** | Compare multiple ML models and rank by performance | 🔴 High |
| **SHAP Feature Importance** | Generate SHAP plots (summary, waterfall, dependence) | 🔴 High |
| **Prediction API** | Make predictions on new data using best model | 🟡 Medium |
| **Frontend ML Dashboard** | Display model performance, feature importance, predictions | 🟡 Medium |

### 3.2 Architecture for Device Independence

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEVICE-INDEPENDENT ML ARCHITECTURE            │
│                                                                   │
│  Frontend (Vercel)            Python ML Backend (Railway/Render) │
│  ┌──────────────────┐         ┌──────────────────────────┐      │
│  │ Next.js + React   │ ──HTTP─▶│  FastAPI + PyCaret       │      │
│  │ ML Dashboard UI   │◀────────│  + SHAP + XGBoost       │      │
│  │ (Responsive)      │         │                          │      │
│  └──────────────────┘         └──────────────────────────┘      │
│         │                              │                         │
│         │                              │                         │
│  ┌──────▼──────┐              ┌───────▼───────┐                │
│  │ Convex DB   │              │  PostgreSQL   │                │
│  │ (metadata)  │              │  (model data) │                │
│  └─────────────┘              └───────────────┘                │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Key Design Decisions

| Requirement | Solution | Why |
|-------------|----------|-----|
| ML model training | Python (PyCaret) - deployed to Railway/Render | Python is required for scikit-learn, SHAP, XGBoost |
| API communication | FastAPI → Convex action via HTTP | Convex actions can make external HTTP calls |
| Model storage | PostgreSQL or joblib files + cloud storage | Models are large binary files |
| Result display | Recharts/Plotly.js for charts | Device-independent SVG rendering |
| Cost | Railway: $5-10/month, Render: $7/month | Minimal cost for ML hosting |

### 3.4 GitHub Repositories

| Repository | Stars | Purpose |
|------------|-------|---------|
| [pycaret/pycaret](https://github.com/pycaret/pycaret) | 9k+ | Low-code AutoML with built-in SHAP support |
| [shap/shap](https://github.com/shap/shap) | 23k+ | Game-theoretic ML explanations |
| [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | 80k+ | High-performance Python API framework |

---

## 4. V4: Multi-Dataset Joins & Cross-Dataset Relationships

### 4.1 What Needs to Be Built

| Component | Description | Complexity |
|-----------|-------------|------------|
| **DatasetRelation Table** | New Convex table storing relationships between datasets | 🟢 Easy |
| **Join Engine** | Support LEFT, INNER, RIGHT, OUTER joins on selected columns | 🟡 Medium |
| **Cross-Dataset Entity Resolution** | LLM-powered matching of entities across datasets | 🟡 Medium |
| **Unified Query Layer** | NLQ that queries across multiple joined datasets | 🟡 Medium |
| **Join UI** | Visual interface for selecting datasets and columns to join | 🟡 Medium |

### 4.2 Architecture for Device Independence

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEVICE-INDEPENDENT JOIN ARCHITECTURE          │
│                                                                   │
│  Frontend UI                         Convex Backend              │
│  ┌──────────────────────┐           ┌──────────────────────┐    │
│  │ Join Configuration UI│           │  datasets table      │    │
│  │ • Select datasets    │──────────▶│  datasetRelations    │    │
│  │ • Choose columns     │◀──────────│  table               │    │
│  │ • Pick join type     │           │                      │    │
│  └──────────────────────┘           │  + pipeline/stage5   │    │
│                                      │  (join orchestrator)│    │
│  ┌──────────────────────┐           └──────────────────────┘    │
│  │ Result Display       │                                        │
│  │ • Table view         │                                        │
│  │ • Chart view         │                                        │
│  │ • Export button      │                                        │
│  └──────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 Key Design Decisions

| Requirement | Solution | Why |
|-------------|----------|-----|
| Join execution | In-memory JavaScript (same as current NLQ SQL engine) | Works within Convex, no external services |
| Entity matching | OpenRouter LLM (qwen/qwen3-coder) | Already integrated, $0 cost |
| Data volume | Limit to 10,000 rows per dataset | Convex free tier limit |
| UI for joins | React table with column selectors | Responsive on all devices |
| Persistence | New `datasetRelations` table in Convex schema | Serverless, auto-syncs |

### 4.4 Implementation Plan

```
Week 1: Schema & Backend
  ├── Add datasetRelations table to convex/schema.ts
  ├── Create mutation: createDatasetRelation
  ├── Create action: executeJoin (LEFT/INNER/RIGHT/OUTER)
  └── Add LLM entity resolution for cross-dataset matching

Week 2: Frontend UI
  ├── Create /data/joins page
  ├── Build dataset selector with checkbox UI
  ├── Build join configuration (column + type selector)
  └── Display joined results in table + chart
```

---

## 5. V5: Enterprise SSO + Natural Language Report Editing

### 5.1 What Needs to Be Built

#### 5.1a Enterprise SSO/SAML

| Component | Description | Complexity |
|-----------|-------------|------------|
| **SAML Identity Provider** | Support Okta, Azure AD, Google Workspace SSO | 🟡 Medium |
| **OAuth2/OIDC Integration** | Google, GitHub, Microsoft login | 🟢 Easy |
| **Role Mapping** | Map SSO groups to app roles (Admin/Analyst/Viewer) | 🟡 Medium |
| **User Provisioning** | Auto-create users on first SSO login | 🟢 Easy |

#### 5.1b Natural Language Report Editing

| Component | Description | Complexity |
|-----------|-------------|------------|
| **AI Report Editor** | Edit any report section with natural language instructions | 🔴 High |
| **Context-Aware Editing** | Select text → describe changes → AI rewrites | 🔴 High |
| **Version History** | Track edits and allow revert | 🟡 Medium |
| **Streaming Responses** | Real-time AI response as user edits | 🟡 Medium |

### 5.2 Architecture for Device Independence

```
┌──────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE SSO ARCHITECTURE                   │
│                                                                   │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐              │
│  │ Okta    │    │ Azure AD │    │ Google Workspace│              │
│  │ (SAML)  │    │ (SAML)   │    │ (OIDC)        │              │
│  └────┬────┘    └────┬─────┘    └──────┬────────┘              │
│       │              │                 │                         │
│       └──────────────┼─────────────────┘                         │
│                      │                                            │
│               ┌──────▼──────┐                                    │
│               │  Auth0 /     │                                    │
│               │  WorkOS     │  (SAML Proxy)                      │
│               └──────┬──────┘                                    │
│                      │                                            │
│               ┌──────▼──────┐                                    │
│               │ Convex Auth │                                    │
│               │ auth.config │                                    │
│               └─────────────┘                                    │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    NL REPORT EDITING ARCHITECTURE                │
│                                                                   │
│  ┌──────────────────────┐    ┌──────────────────────────┐       │
│  │ react-markdown       │    │ OpenRouter (qwen)        │       │
│  │ Editable text        │───▶│ + context prompt         │       │
│  │ Selection → Edit     │◀───│ → AI generates new text  │       │
│  └──────────────────────┘    └──────────────────────────┘       │
│         │                                                       │
│         │                                                        │
│  ┌──────▼──────┐                                                │
│  │ Convex DB   │                                                │
│  │ + version   │                                                │
│  │ history     │                                                │
│  └─────────────┘                                                │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Key Design Decisions

| Requirement | Solution | Why |
|-------------|----------|-----|
| SSO for multiple providers | Auth0 or WorkOS as SAML proxy | Handles Okta, Azure AD, Google with one integration |
| Convex auth integration | Update `convex/auth.config.ts` | Convex has built-in auth provider support |
| Report editing UI | react-markdown with custom plugins | Already in dependencies, responsive |
| AI edit prompting | OpenRouter with context window | Already integrated, $0 cost |
| Version history | New `reportVersions` Convex table | Serverless, auto-syncs across devices |

### 5.4 GitHub Repositories

| Repository | Stars | Purpose |
|------------|-------|---------|
| [auth0/nextjs-auth0](https://github.com/auth0/nextjs-auth0) | 2k+ | Next.js SSO integration with multiple providers |
| [workos-inc/workos-node](https://github.com/workos-inc/workos-node) | 200+ | Enterprise SSO (Okta, Azure AD, Google) |
| [remarkjs/react-markdown](https://github.com/remarkjs/react-markdown) | 13k+ | Already in project — use for editable reports |

---

## 6. Device-Independent Platform Architecture

### 6.1 Core Requirements

AutoInsight AI is already **device-independent** because:
- ✅ **Tailwind CSS** responsive design (mobile-first breakpoints)
- ✅ **PWA** with service worker and offline support
- ✅ **Vercel CDN** for global low-latency access
- ✅ **Convex Cloud** for serverless real-time sync
- ✅ **Touch-friendly** UI (upload page supports touch events)

### 6.2 V2-V5 Must Maintain This

| Requirement | How to Maintain | Check |
|-------------|----------------|-------|
| Responsive grid charts | react-grid-layout breaks into single-column on mobile | ✅ |
| Touch drag-and-drop | react-grid-layout + dnd-kit support touch natively | ✅ |
| Offline access | PWA caches dashboard layouts + reports | ✅ |
| Real-time sync | Convex auto-syncs layout changes across devices | ✅ |
| Small screen | All new pages tested at 320px, 768px, 1280px+ | ⬜ |
| Accessibility | WCAG 2.1 AA compliance for all new UI | ⬜ |

### 6.3 Device Testing Matrix

| Feature | Desktop (1920px) | Laptop (1366px) | Tablet (768px) | Phone (375px) |
|---------|-----------------|-----------------|---------------|--------------|
| Chart Builder | 4-column grid | 3-column grid | 2-column grid | 1-column stack |
| Email Scheduling | Full form | Full form | Stacked form | Modal overlay |
| ML Dashboard | Sidebar + charts | Sidebar + charts | Top nav + charts | Single column |
| Join UI | Table + config | Table + config | Stacked config | Wizard mode |
| SSO Login | Centered card | Centered card | Full-width card | Full-screen |
| Report Editor | Side-by-side | Side-by-side | Stacked edit | Full-screen editor |

---

## 7. GitHub Repository Recommendations (Master List)

### 🟢 V2: Chart Builder + Email

| Repository | Stars | Purpose | Link |
|------------|-------|---------|------|
| **react-grid-layout/react-grid-layout** | 20k+ | Drag-and-drop responsive grid (handles both layout AND drag internally) | [GitHub](https://github.com/react-grid-layout/react-grid-layout) |
| **clauderic/dnd-kit** | 13k+ | Only needed if adding sidebar-to-grid dragging (V3+ enhancement) | [GitHub](https://github.com/clauderic/dnd-kit) |
| **recharts/recharts** | 24k+ | React charting library (SVG) | [GitHub](https://github.com/recharts/recharts) |
| **resend/react-email** | 14k+ | Build and send emails with React | [GitHub](https://github.com/resend/react-email) |
| **calcom/cal.com** | 34k+ | Open-source scheduling (Next.js) | [GitHub](https://github.com/calcom/calcom) |

### 🟠 V3: ML Integration

| Repository | Stars | Purpose | Link |
|------------|-------|---------|------|
| **pycaret/pycaret** | 9k+ | Low-code AutoML with SHAP built-in | [GitHub](https://github.com/pycaret/pycaret) |
| **shap/shap** | 23k+ | Game-theoretic ML explanations | [GitHub](https://github.com/shap/shap) |
| **tiangolo/fastapi** | 80k+ | Python API framework (deploy on Railway) | [GitHub](https://github.com/tiangolo/fastapi) |

### 🔵 V4: Multi-Dataset Joins

| Repository | Stars | Purpose | Link |
|------------|-------|---------|------|
| No external repos needed | — | Build join engine in Convex/JS | — |

### 🟣 V5: Enterprise SSO + NL Editing

| Repository | Stars | Purpose | Link |
|------------|-------|---------|------|
| **auth0/nextjs-auth0** | 2k+ | Next.js SSO with multiple providers | [GitHub](https://github.com/auth0/nextjs-auth0) |
| **workos-inc/workos-node** | 200+ | Enterprise SSO (Okta, Azure AD, SAML) | [GitHub](https://github.com/workos-inc/workos-node) |
| **remarkjs/react-markdown** | 13k+ | Already in project — edit reports | [GitHub](https://github.com/remarkjs/react-markdown) |

### 🚀 Deployment & Infrastructure

| Repository | Stars | Purpose | Link |
|------------|-------|---------|------|
| **railwayapp/railway** | — | Deploy Python ML microservice ($5/mo) | [railway.app](https://railway.app) |
| **convex-dev/convex** | — | Serverless DB + functions (free $0) | [convex.dev](https://convex.dev) |
| **vercel/vercel** | — | Frontend hosting (free $0) | [vercel.com](https://vercel.com) |

---

## 8. Implementation Timeline & Priority

### Recommended Order

```
Priority:     HIGH          MEDIUM           LOWER
             ┌─────┐      ┌──────┐       ┌────────┐
Week 1-2:    │ V2  │      │      │       │        │
             │     │      │      │       │        │
Week 3-4:    │ V2  │      │ V4   │       │        │
             │     │      │      │       │        │
Week 5-7:    │     │      │      │       │ V3     │
             │     │      │      │       │        │
Week 8-9:    │ V5a │      │      │       │        │
             │SSO  │      │      │       │        │
Week 10-12:  │ V5b │      │      │       │        │
             │NL Ed│      │      │       │        │
             └─────┘      └──────┘       └────────┘
```

### Cost Analysis

| Feature | Development Cost | Monthly Operating Cost |
|---------|-----------------|----------------------|
| **V2:** Chart Builder | Free (open-source libs) | $0 |
| **V2:** Email Reports | Free (Resend free tier) | $0 (100 emails/day) |
| **V3:** ML Microservice | Free | $5-10/mo (Railway) |
| **V4:** Multi-Dataset Joins | Free | $0 |
| **V5:** SSO (Auth0) | Free | $0 (up to 7k users) |
| **V5:** SSO (WorkOS SAML) | Free | $0 (up to 10 users) |
| **V5:** NL Report Editing | Free (OpenRouter) | $0 |
| **Total** | **$0** | **$5-10/month** |

---

## Appendix A: Monitoring & Observability Notes

When adding V3 (ML microservice), add a monitoring strategy:
- Railway provides built-in logs and metrics dashboard
- Add a `/health` endpoint to the FastAPI ML service
- Convex can monitor the HTTP calls via its dashboard
- Set up simple error alerting via email when ML service returns 5xx

## Appendix B: Convex Built-in Auth vs External SSO

For V5 SSO, use the simplest solution that meets your needs:

| Auth Type | Solution | Cost | Effort |
|-----------|----------|------|--------|
| Email/Password (Current) | Convex + bcrypt | $0 | Already done |
| Google/GitHub OAuth | Convex built-in (update `auth.config.ts`) | $0 | 1 hour |
| Okta/Azure AD SAML | Auth0 or WorkOS proxy | $0-100/mo | 3-5 days |

**Recommendation:** Start with Convex's built-in Google/GitHub OAuth for V5 SSO. Only add Auth0/WorkOS if enterprise customers specifically require SAML.

## Appendix C: Quick-Start Commands for Each Feature

### V2: Chart Builder
```bash
cd frontend
npm install react-grid-layout recharts @types/react-grid-layout
# Then build: ChartPalette, DashboardCanvas, save layout to Convex
```

### V2: Email Scheduling
```bash
npm install resend
# Then build: ScheduleReport UI + Convex action sendScheduledReport
```

### V3: ML Microservice
```bash
mkdir ml-service && cd ml-service
pip install fastapi uvicorn pycaret shap xgboost scikit-learn
# Deploy to Railway: git push railway main
```

### V4: Multi-Dataset Joins
```bash
# No install needed — pure Convex/JS
# Add schema: datasetRelations table
# Build: executeJoin action + join UI page
```

### V5: SSO
```bash
npm install @auth0/nextjs-auth0
# Update: convex/auth.config.ts + AuthContext.tsx
```

### V5: NL Report Editing
```bash
# Already have react-markdown in dependencies
# Add: edit mode toggle + AI edit button + version history
```

---

*Generated for AutoInsight AI v1.0 → Future Roadmap — June 2026*
