# 🔧 AutoInsight AI — Complete Technical Report

> **Everything You Need to Know — Database, Architecture, Deployment, Code Structure**
> 
> Read this report once and you will have **zero confusion** about the entire technical implementation.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Database Schema (9 Tables Explained)](#3-database-schema-9-tables-explained)
4. [Frontend Pages (9 Pages Explained)](#4-frontend-pages-9-pages-explained)
5. [Backend: Convex Server Functions](#5-backend-convex-server-functions)
6. [Backend: Python FastAPI (Local Dev)](#6-backend-python-fastapi-local-dev)
7. [4-Stage Data Pipeline](#7-4-stage-data-pipeline)
8. [8-Agent Report Engine](#8-8-agent-report-engine)
9. [LLM Provider: OpenRouter + Groq](#9-llm-provider-openrouter--groq)
10. [Authentication System](#10-authentication-system)
11. [File Upload System](#11-file-upload-system)
12. [NLQ Chat System](#12-nlq-chat-system)
13. [Dashboard System](#13-dashboard-system)
14. [Export Formats](#14-export-formats)
15. [PWA & Offline](#15-pwa--offline)
16. [Audit Logging](#16-audit-logging)
17. [PII Auto-Masking](#17-pii-auto-masking)
18. [CI/CD Pipeline](#18-cicd-pipeline)
19. [Environment Variables](#19-environment-variables)
20. [Testing](#20-testing)
21. [Deployment Steps](#21-deployment-steps)
22. [File Tree (Complete)](#22-file-tree-complete)

---

## 1. Project Overview

```
Name:           AutoInsight AI
Version:        1.0.0
Purpose:        AI-Powered Data Analysis Platform
Frontend:       Next.js 14 (React 18) → Hosted on Vercel
Backend:        Convex Cloud (BaaS) — Serverless Database + Functions
LLM Provider:   OpenRouter API (Primary) → Groq API (Fallback)
Cost:           $0/month (All services on free tiers)
```

---

## 2. System Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                               │
│                  (Any device — Phone, Tablet, Laptop)                │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         VERCEL (CDN)                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Next.js 14 Frontend (React 18)                   │   │
│  │                                                               │   │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────┐  │   │
│  │  │ Upload  │ │Dashboard │ │ Reports  │ │ NLQ     │ │Admin│  │   │
│  │  │ Page    │ │ Page     │ │ Page     │ │ Chat    │ │Page │  │   │
│  │  └─────────┘ └──────────┘ └──────────┘ └──────────┘ └─────┘  │   │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │   │
│  │  │ Login   │ │Register  │ │ System   │ │ Offline  │          │   │
│  │  │ Page    │ │ Page     │ │ Status   │ │ Page     │          │   │
│  │  └─────────┘ └──────────┘ └──────────┘ └──────────┘          │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │  Components: ChartWidget, DashboardGrid, FilterBar,    │  │   │
│  │  │  Layout, RequireAuth, ReportExport                     │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     CONVEX CLOUD (Backend as a Service)              │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    DATABASE (9 Tables)                        │   │
│  │                                                               │   │
│  │  users ─── hasMany ──▶ uploads ─── hasOne ──▶ pipelineResults │   │
│  │    │                      │                                     │   │
│  │    │                      ├──────────▶ reports                  │   │
│  │    │                      ├──────────▶ dashboards               │   │
│  │    │                      ├──────────▶ conversations ──▶ NLQ    │   │
│  │    │                      └──────────▶ datasets                 │   │
│  │    │                                                              │   │
│  │    └───────────────▶ auditLog  (Every user action logged)       │   │
│  │                                                                   │   │
│  │  prompts  (Versioned prompt templates for AI)                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              SERVER FUNCTIONS (20+ TypeScript Files)          │   │
│  │                                                               │   │
│  │  ┌─────────────┐ ┌───────────┐ ┌────────┐ ┌──────────────┐  │   │
│  │  │  Pipeline   │ │  Reports  │ │ NLQ   │ │  Users/Auth  │  │   │
│  │  │  Stage 1-4  │ │  8 Agents │ │ Chat  │ │  + Uploads   │  │   │
│  │  └─────────────┘ └───────────┘ └────────┘ └──────────────┘  │   │
│  │  ┌─────────────┐ ┌───────────┐ ┌────────────────────────┐  │   │
│  │  │  Audit Log  │ │Dashboards │ │  lib/openrouter.ts     │  │   │
│  │  │             │ │           │ │  (3-tier LLM fallback) │  │   │
│  │  └─────────────┘ └───────────┘ └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    LLM PROVIDERS (3-Tier Fallback)                   │
│                                                                      │
│  1st: OpenRouter qwen/qwen3-coder:free      (Primary)               │
│  2nd: OpenRouter meta-llama/llama-4-maverick:free (Fallback)        │
│  2nd: OpenRouter meta-llama/llama-4-maverick:free (Fallback)             │
│                                                                      │
│  All are $0/month — completely free                                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema (9 Tables Explained)

### Table 1: `users` — User Accounts

```
Fields:
  email:        string          → User's email address (unique)
  name:         string          → User's display name
  passwordHash: string          → bcrypt-hashed password
  role:         "admin" | "analyst" | "viewer"  → Access level
  createdAt:    number          → Unix timestamp of account creation
  lastLogin:    number (optional) → Last login timestamp

Indexes:
  by_email → Quick lookup by email

Purpose: Store user accounts and authentication data
```

### Table 2: `uploads` — File Uploads

```
Fields:
  userId:        id("users")    → Who uploaded this file
  fileName:      string         → Original file name
  fileSize:      number         → File size in bytes
  fileStorageId: string (optional) → Convex Storage reference
  status:        "pending" | "uploading" | "processing" | "completed" | "failed"
  rowCount:      number (optional) → Number of rows in CSV
  columnCount:   number (optional) → Number of columns in CSV
  createdAt:     number         → Upload timestamp
  completedAt:   number (optional) → Processing completion timestamp

Indexes:
  by_user → Find all uploads by a user

Purpose: Track file upload metadata and processing status
```

### Table 3: `pipelineResults` — Pipeline Output

```
Fields:
  uploadId:          id("uploads")  → Which upload this belongs to
  userId:            id("users")    → Who triggered the pipeline
  status:            "queued" | "running" | "completed" | "failed"
  schemaInference:   any (optional) → Stage 1 output (column types, names)
  cleaningPlan:      any (optional) → Stage 2 output (cleaning operations)
  unifiedDataModel:  any (optional) → Stage 3 output (relationships)
  processingTimeMs:  number (optional) → Total processing time
  error:             string (optional) → Error message if failed
  createdAt:         number         → Pipeline start timestamp

Indexes:
  by_upload → Find pipeline result for a specific upload

Purpose: Store the output of the 4-stage data pipeline
```

### Table 4: `reports` — Generated Reports

```
Fields:
  uploadId:          id("uploads")    → Source data
  userId:            id("users")      → Report owner
  title:             string           → Report title
  sections:          array of objects → 8 sections from AI agents
  overallConfidence: number           → Average confidence (0.0 to 1.0)
  exportFormats:     array of strings (optional) → Generated formats
  createdAt:         number           → Report generation timestamp

  Section object:
    sectionType: string    → "business_context" | "data_profiling" | etc.
    title:       string    → Section heading
    content:     string    → Full section content (Markdown)
    confidence:  number    → AI confidence score (0.0 to 1.0)

Indexes:
  by_user → Find all reports by a user

Purpose: Store AI-generated reports with all 8 sections
```

### Table 5: `dashboards` — Dashboard Layouts

```
Fields:
  uploadId:  id("users")    → Source data
  userId:    id("users")    → Dashboard owner
  title:     string         → Dashboard title
  layout:    array of objects → Grid layout (x, y, w, h, i)
  widgets:   any            → Chart configurations and data
  createdAt: number         → Dashboard creation timestamp

Indexes:
  by_user → Find all dashboards by a user

Purpose: Store dashboard configurations and chart data
```

### Table 6: `conversations` — NLQ Chat History

```
Fields:
  userId:    id("users")    → Who is chatting
  uploadId:  id("uploads")  → Which dataset they're querying
  messages:  array of objects → Chat history (up to 20 turns)

  Message object:
    role:        "user" | "assistant"
    content:     string         → Message text
    sqlGenerated: string (optional) → SQL query generated
    chartConfig:  any (optional) → Chart config for visualization
    timestamp:   number         → Message timestamp

  createdAt: number  → Conversation start
  updatedAt: number  → Last message timestamp

Indexes:
  by_user_upload → Find conversations for a specific user+dataset

Purpose: Store NLQ chat history for each user+dataset combination
```

### Table 7: `datasets` — Raw Data Storage

```
Fields:
  uploadId:  id("uploads")  → Source upload
  userId:    id("users")    → Data owner
  columns:   array of strings → Column names
  rowCount:  number         → Row count
  data:      any            → Actual data (stored as JSON)
  createdAt: number         → Storage timestamp

Indexes:
  by_upload → Find dataset for a specific upload

Purpose: Store the parsed CSV data for querying and analysis
```

### Table 8: `auditLog` — Enterprise Audit Trail

```
Fields:
  userId:       id("users")         → Who performed the action
  action:       string              → What action was taken
  resourceType: string              → What was affected
  resourceId:   string (optional)   → Specific resource ID
  details:      any (optional)      → Extra context
  ip:           string (optional)   → IP address
  timestamp:    number              → When it happened

Indexes:
  by_user       → Find all actions by a user
  by_resource   → Find all actions on a resource
  by_timestamp  → Find actions in a time range

Purpose: Enterprise compliance — every action is logged forever
```

### Table 9: `prompts` — AI Prompt Templates

```
Fields:
  name:      string    → Prompt name (e.g., "report_business_context")
  version:   number    → Version number (incremented on changes)
  template:  string    → The actual prompt template
  provider:  string    → Which llm provider (openrouter / groq)
  createdAt: number    → Creation timestamp

Indexes:
  by_name → Find latest version of a named prompt

Purpose: Store versioned AI prompts for reproducibility
```

### Entity Relationships Diagram

```
users (1) ────── hasMany ──────▶ uploads (many)
                                   │
                                   ├── hasOne ──▶ pipelineResults
                                   ├── hasOne ──▶ reports
                                   ├── hasOne ──▶ dashboards
                                   ├── hasMany ─▶ conversations
                                   └── hasOne ──▶ datasets

users (1) ────── hasMany ──────▶ auditLog (many)
```

---

## 4. Frontend Pages (9 Pages Explained)

### Page 1: Home/Landing (`/`)

```
File:       src/app/page.tsx
Purpose:    Redirects users to Dashboard (if logged in) or Login (if not)
Type:       Client Component ("use client")
Key Code:   useRouter() + useAuth() → conditional redirect
```

### Page 2: Login (`/auth/login`)

```
File:       src/app/auth/login/page.tsx
Purpose:    User login with email + password
Flow:       Enter credentials → API call → Success → Redirect to Dashboard
Security:   JWT tokens stored in localStorage
```

### Page 3: Register (`/auth/register`)

```
File:       src/app/auth/register/page.tsx
Purpose:    New user registration
Flow:       Enter name + email + password → API call → Auto-login → Dashboard
```

### Page 4: Dashboard (`/dashboard`)

```
File:       src/app/dashboard/page.tsx
Purpose:    Main analytics dashboard with KPI cards and charts
Features:   • Auto-generated KPIs from report data
            • Interactive Plotly charts (bar, line, pie, scatter)
            • Drill-down: Click chart elements to explore data
            • Responsive grid layout
Components: ChartWidget, DashboardGrid, FilterBar
```

### Page 5: Upload (`/upload`)

```
File:       src/app/upload/page.tsx
Purpose:    File upload interface for CSV data
Features:   • Drag-and-drop file selection (react-dropzone)
            • Upload progress bar
            • File validation (CSV only, 100MB max)
            • Automatic pipeline trigger after upload
```

### Page 6: Reports (`/reports/[id]`)

```
File:       src/app/reports/[id]/page.tsx
Purpose:    View and export AI-generated reports
Features:   • 8-section report display with confidence badges
            • Export buttons: HTML, Markdown, PDF, Excel
            • Section-by-section confidence indicators
Components: ReportExport (handles all 4 export formats)
```

### Page 7: NLQ Chat (`/nlq`)

```
File:       src/app/nlq/page.tsx
Purpose:    Natural language query interface
Features:   • Chat-style interface (like ChatGPT)
            • 20-turn conversation history
            • SQL query generation behind the scenes
            • Chart visualization for data results
```

### Page 8: Admin (`/admin`)

```
File:       src/app/admin/page.tsx
Purpose:    Admin user management
Access:     Admin role only
Features:   • List all users
            • View user details
            • Manage roles
```

### Page 9: System Status (`/system`) — NEW

```
File:       src/app/system/page.tsx
Purpose:    System health monitoring dashboard
Features:   • Service health cards (Convex, OpenRouter, Storage)
            • Application version & build info
            • All 9 database tables listed
            • Architecture diagram
            • LLM provider status
```

### Extra: Offline Page (`/offline`)

```
File:       src/app/offline/page.tsx
Purpose:    PWA offline fallback when no internet
Trigger:    Service worker intercepts failed navigation requests
```

---

## 5. Backend: Convex Server Functions

### File Structure

```
convex/
├── schema.ts                 → Database schema definition (9 tables)
├── auth.config.ts            → Auth provider configuration
├── users.ts                  → 4 queries + 4 mutations for user management
│   ├── queries: getUser, listUsers, getUserByEmail
│   └── mutations: createUser, updateUser, updateUserRole, deleteUser
│
├── uploads.ts                → 2 queries + 3 mutations for file uploads
│   ├── queries: getUpload, listUploads
│   └── mutations: createUpload, updateUploadStatus, deleteUpload
│
├── datasets.ts               → Query + mutation for data storage
│   ├── query: getDataset
│   └── mutation: storeDataset
│
├── reports.ts                → Report engine (CRITICAL FILE)
│   ├── query: getReport, listReports
│   ├── mutation: generateReport (triggers 8 AI agents)
│   └── action: exportReport (generates export content)
│   └── Confidence gating: ≥0.65 threshold, 3 retries with temperature
│
├── nlq.ts                    → NLQ chat engine (CRITICAL FILE)
│   ├── action: chat (processes natural language query)
│   └── mutations: createConversation, addMessage, getConversation
│
├── dashboards.ts             → Dashboard generation
│   ├── action: generateDashboard
│   └── query: getDashboard
│
├── audit.ts                  → Audit log (NEW)
│   ├── mutation: logAction
│   └── query: listAuditLogs
│
├── pipeline/
│   ├── index.ts              → Orchestrator (runs stages sequentially)
│   ├── stage1.ts             → Schema inference using AI
│   ├── stage2.ts             → Data cleaning + PII masking
│   ├── stage3.ts             → LangGraph entity extraction
│   └── stage4.ts             → Column engine (derived metrics)
│
└── lib/
    ├── openrouter.ts         → LLM client (PRIMARY)
    │   └── 3-tier fallback:
    │       1st: OpenRouter qwen/qwen3-coder:free
    │       2nd: OpenRouter llama-4-maverick:free
    │       3rd: Groq llama-3.3-70b-versatile
    │
    ├── groq.ts               → DEPRECATED (fallback inline in openrouter.ts)
    │
    └── export_templates.ts   → HTML + Markdown export generators
```

### How Convex Works

```
User's Browser                    Convex Cloud
┌────────────┐                   ┌──────────────────────┐
│ useQuery() │ ──── query ─────▶ │  Query Function      │
│            │ ◀─── result ───── │  (reads from DB)     │
│            │                   │                      │
│ useMutation│ ──── mutate ────▶ │  Mutation Function   │
│            │ ◀─── response ─── │  (writes to DB)      │
│            │                   │                      │
│ useAction() │ ── action ─────▶│  Action Function      │
│            │ ◀─── result ───── │  (HTTP calls to LLM) │
└────────────┘                   └──────────────────────┘
```

**Key Difference:**
- **Queries** → Read data (realtime, cached)
- **Mutations** → Write data (goes through consensus)
- **Actions** → Run side effects (HTTP calls to OpenRouter/Groq)

---

## 6. Backend: Python FastAPI (Local Dev Only)

The `backend/` folder contains a Python FastAPI implementation **for local development only**.

In production:
- ✅ **Convex Cloud** replaces the Python backend
- ✅ **No PostgreSQL, Redis, MinIO, Celery needed**
- ✅ Everything runs serverlessly on Convex

The Python backend is kept for:
- **Reference** — Understanding the original design
- **Local testing** — If you want to run without Convex
- **Migration path** — If you want to move to a different backend

---

## 7. 4-Stage Data Pipeline

### Stage 1: Schema Inference

```
File:     convex/pipeline/stage1.ts
Input:    Raw CSV data
Process:  AI analyzes column names + sample values
Output:   Detected schema (column names, types, descriptions)
AI Model: OpenRouter qwen/qwen3-coder:free
```

### Stage 2: Data Cleaning + PII Masking

```
File:     convex/pipeline/stage2.ts
Input:    Raw data + schema from Stage 1
Process:
  1. PII Detection (auto-mask sensitive data):
     • Email addresses → j***@***.com (first char + ***@*** + domain)
     • Phone numbers  → *******4567 (last 4 digits visible)
     • SSN numbers    → ***-**-6789 (last 4 digits visible)
     • Credit cards   → ****-****-****-1111 (last 4 digits visible)
  2. Data cleaning: missing values, outliers, duplicates
Output:   Cleaned data + cleaning plan
AI Model: OpenRouter qwen/qwen3-coder:free
```

### Stage 3: LangGraph Entity Extraction

```
File:     convex/pipeline/stage3.ts
Input:    Cleaned data + schema
Process:  AI extracts entities, relationships, patterns
Output:   Unified data model (entities + relationships)
AI Model: OpenRouter qwen/qwen3-coder:free
```

### Stage 4: Column Engine

```
File:     convex/pipeline/stage4.ts
Input:    Unified data model
Process:  AI suggests derived metrics and aggregations
Output:   Final processed data with derived columns
AI Model: OpenRouter qwen/qwen3-coder:free
```

---

## 8. 8-Agent Report Engine

### The 8 AI Agents

Each agent is a specialized "expert" that writes one section of the report:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REPORT ENGINE                                  │
│                                                                     │
│  Agent 1: Business Context    → Industry context, domain insights   │
│  Agent 2: Data Profiling      → Column stats, distributions        │
│  Agent 3: Data Quality        → Missing values, outliers, issues   │
│  Agent 4: EDA                 → Visual patterns, correlations      │
│  Agent 5: Statistical Analysis → Hypothesis tests, significance    │
│  Agent 6: Visualization       → Chart recommendations              │
│  Agent 7: Insights            → Actionable business insights       │
│  Agent 8: Recommendations     → Data-driven recommendations        │
│                                                                     │
│  File: convex/reports.ts                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Confidence Gating

Every AI-generated section goes through confidence validation:

```
                           ┌─────────────┐
                           │ AI generates │
                           │   content    │
                           └──────┬──────┘
                                  │
                                  ▼
                           ┌─────────────┐
                           │  Calculate   │
                           │  confidence  │
                           └──────┬──────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ≥ 0.65          < 0.65      Failed 3x
              ┌──────┐    ┌──────────┐   ┌──────────┐
              │Auto- │    │Retry with│   │ Fallback │
              │Accept│    │higher    │   │ to safe  │
              └──────┘    │temp (0.3)│   │ text     │
                          └──────────┘   └──────────┘
                               │
                          (2 more retries if needed
                          at temperatures 0.3, 0.5)
```

---

## 9. LLM Provider: OpenRouter + Groq

### Architecture

```
File:     convex/lib/openrouter.ts
Purpose:  Single entry point for ALL AI calls in the app
Models:
  1st: OpenRouter qwen/qwen3-coder:free        (Primary)
  2nd: OpenRouter meta-llama/llama-4-maverick:free (Fallback)
  3rd: Groq llama-3.3-70b-versatile            (Emergency)
```

### Fallback Logic Flow

```
callLLM(apiKey, systemPrompt, userPrompt)
│
├── Attempt 1: OpenRouter (qwen/qwen3-coder:free)
│   ├── Success → Return result
│   └── Failure → Log warning, go to Attempt 2
│
├── Attempt 2: OpenRouter (llama-4-maverick:free)
│   ├── Success → Return result
│   └── Failure → Log warning, go to Attempt 3
│
└── Attempt 3: Groq (llama-3.3-70b-versatile)
    ├── Success → Return result
    └── Failure → Throw error (all providers failed)
```

### API Key Priority

```
1. Check: OPENROUTER_API_KEY in environment
2. Fallback: GROQ_API_KEY in environment
```

### Files Using the LLM

| File | How It Uses AI |
|------|----------------|
| `pipeline/stage1.ts` | Infers schema from CSV data |
| `pipeline/stage2.ts` | Generates cleaning plan + PII detection |
| `pipeline/stage3.ts` | Extracts entities and relationships |
| `reports.ts` | Generates all 8 report sections |
| `nlq.ts` | Interprets natural language → generates response |

---

## 10. Authentication System

### How Login Works

```
1. User enters email + password
2. Frontend calls users.ts mutation createUser / authenticateUser
3. Password is hashed with bcrypt before storage
4. JWT tokens (access + refresh) are returned
5. Tokens stored in localStorage
6. Every future API call includes the token in Authorization header
```

### User Roles

| Role | Permissions | Can View |
|------|------------|----------|
| **admin** | Full access | Everything + Admin panel |
| **analyst** | Upload + Analyze | Reports, Dashboard, NLQ |
| **viewer** | Read only | Shared reports, Dashboard |

### Auth Providers (Current)

```
convex/auth.config.ts → providers: []  // No external auth yet
```

You can add Google/GitHub OAuth later by updating this file.

---

## 11. File Upload System

### Upload Flow

```
1. User selects a CSV file (drag-and-drop or click)
2. Frontend creates upload record in Convex (createUpload mutation)
3. File is uploaded to Convex Storage (built-in file storage)
4. Upload status updated: pending → uploading → completed
5. Pipeline automatically triggered after upload completes
6. User can view progress in real-time
```

### File Validations

| Check | Limit |
|-------|-------|
| File type | CSV only |
| File size | 100MB max |
| User storage | Free Convex: 50GB |

---

## 12. NLQ Chat System

### How Chat Works

```
1. User types: "Show me total sales by region"
2. convex/nlq.ts action:
   a. Parse intent using AI
   b. Generate query/data transformation
   c. Execute against dataset
   d. Synthesize natural language response
   e. Generate chart config if applicable
3. Response displayed in chat UI
4. Conversation stored for context (20-turn history)
```

### Conversation Flow

```
User: "Show me total sales by region"
AI:   [Returns: summary text + optional chart]
User: "Filter to only North region"
AI:   [Returns: filtered results]
User: "Sort by highest sales"
AI:   [Returns: sorted results]
     ...continues with context (up to 20 messages)
```

---

## 13. Dashboard System

### How Dashboard Works

```
1. After upload + pipeline → dashboard is auto-generated
2. AI analyzes the data and creates KPI cards:
   • Total rows, columns
   • Missing values percentage
   • Data quality score
3. Charts are generated based on data:
   • Bar charts for categorical data
   • Line charts for trends
   • Pie charts for distributions
   • Scatter plots for correlations
4. Drill-down: Click any chart element to explore details
```

### Dashboard Components

| Component | File | Purpose |
|-----------|------|---------|
| `ChartWidget` | `ChartWidget.tsx` | Interactive Plotly chart with drill-down |
| `DashboardGrid` | `DashboardGrid.tsx` | Responsive grid layout |
| `FilterBar` | `FilterBar.tsx` | Filter controls for data |

---

## 14. Export Formats

### 4 Export Formats Available

| Format | File | Library | How It Works |
|--------|------|---------|-------------|
| **HTML** | `export_templates.ts` + `ReportExport.tsx` | Inline template | Generates full HTML with CSS styling |
| **Markdown** | `export_templates.ts` | Inline template | Clean markdown with all sections |
| **PDF** | `ReportExport.tsx` | `@react-pdf/renderer` | Client-side PDF generation |
| **Excel** | `ReportExport.tsx` | `xlsx` | 2 sheets: Overview + Sections |

### Export Button UI

Located in `ReportExport.tsx` — renders 4 buttons:
```
┌────────────────────────────────┐
│ 📄 HTML    📝 Markdown         │
│ 📕 PDF     📊 Excel            │
└────────────────────────────────┘
```

---

## 15. PWA & Offline

### PWA Files

| File | Purpose |
|------|---------|
| `public/sw.js` | Service worker — caches app shell, serves offline page |
| `public/manifest.json` | Web manifest — allows "Add to Home Screen" |
| `src/app/offline/page.tsx` | Offline fallback page |
| `src/app/layout.tsx` | PWA metadata (apple-touch-icon, theme-color) |

### How Offline Works

```
1. User visits app → Service worker caches core pages
2. User loses internet → Service worker intercepts requests
3. If page is cached → Shows cached version
4. If page is not cached → Shows /offline page
5. User reconnects → App works normally again
```

---

## 16. Audit Logging

### How Auditing Works

```
Every time a user does something important:
→ logAction(userId, action, resourceType, resourceId, details)
→ Stored in auditLog table with timestamp
→ Queryable by user, resource type, or time range
```

### What Gets Logged

| Event | Logged As |
|-------|-----------|
| User login | `action: "login"` |
| User uploads file | `action: "upload"` |
| Pipeline runs | `action: "pipeline.start"` |
| Report generated | `action: "report.generate"` |
| Report exported | `action: "report.export"` |
| Data exported | `action: "data.export"` |

### Audit Log Indexes

- `by_user` → Find everything a user did
- `by_resource` → Find everything that happened to a resource
- `by_timestamp` → Find events in a time range

---

## 17. PII Auto-Masking

### What Gets Masked

| PII Type | Pattern | Example Before | Example After |
|----------|---------|---------------|---------------|
| **Email** | Standard email format | `john@example.com` | `j***@***.com` (first char + ***@*** + domain) |
| **Phone** | International formats | `+1-555-123-4567` | `*******4567` (last 4 visible) |
| **SSN** | XXX-XX-XXXX | `123-45-6789` | `***-**-6789` (last 4 visible) |
| **Credit Card** | 16-digit numbers | `4111-1111-1111-1111` | `****-****-****-1111` (last 4 visible) |

### Where It Happens

```
File: convex/pipeline/stage2.ts
Step: Applied as FIRST step in data cleaning
Why: Before any analysis, sensitive data is protected
```

### Important Note

PII masking keeps the **last 4 digits** of phone, SSN, and credit card numbers for analysis utility (many analyses need to group by last digits without exposing full numbers).

---

## 18. CI/CD Pipeline

### Pipeline Structure

```
File: .github/workflows/ci-cd.yml

on: push to main/develop, PR to main

Jobs:
  1. quality (ubuntu-latest)
     ├── npm ci
     ├── npx tsc --noEmit (TypeScript check)
     └── npm run lint (ESLint)

  2. deploy-convex (needs: quality, if: main branch)
     ├── npm ci
     └── convex-dev/action (deploys to Convex Cloud)

  3. deploy-vercel (needs: quality, if: main branch)
     └── amondnet/vercel-action (deploys to Vercel)
```

### Required GitHub Secrets

| Secret | How to Get |
|--------|------------|
| `CONVEX_DEPLOY_KEY` | `cd frontend && npx convex deploy-key` |
| `VERCEL_TOKEN` | vercel.com/account/tokens → Create |
| `VERCEL_ORG_ID` | Vercel project → Settings → IDs |
| `VERCEL_PROJECT_ID` | Vercel project → Settings → IDs |

---

## 19. Environment Variables

### All Environment Variables

| Variable | Required | Where | Purpose |
|----------|----------|-------|---------|
| `NEXT_PUBLIC_CONVEX_URL` | ✅ Yes | `.env.local` + Vercel | Convex deployment URL |
| `OPENROUTER_API_KEY` | ✅ Yes | `.env.local` + Vercel | OpenRouter API key |
| `GROQ_API_KEY` | ❌ Optional | `.env.local` + Vercel | Groq fallback API key |
| `NEXT_PUBLIC_API_URL` | ❌ Optional | `.env.local` only | Local dev backend URL |
| `NEXT_PUBLIC_APP_URL` | ❌ Optional | `.env.local` + Vercel | App URL for OpenRouter referer |

### Where to Get Each Key

```
NEXT_PUBLIC_CONVEX_URL → https://dashboard.convex.dev → Your project → Settings
OPENROUTER_API_KEY    → https://openrouter.ai/keys → Create API Key
GROQ_API_KEY          → https://console.groq.com/keys → Create API Key
```

---

## 20. Testing

### Test Configuration

```
Framework:  Vitest
Config:     frontend/vitest.config.ts
Test files: src/**/*.test.ts, convex/**/*.test.ts
Timeouts:   30s per test
```

### Current Tests

| Test File | Tests | Status |
|-----------|-------|--------|
| `src/lib/utils.test.ts` | 21 tests | ✅ All Pass (763ms) |

### Run Tests

```bash
cd frontend && npx vitest run
```

### Python Backend Tests (for local development)

```bash
pytest tests/
# Tests: test_auth.py, test_pipeline_orchestrator.py,
#         test_report_engine.py, test_schemas.py, test_tools.py
```

### E2E Tests

```bash
cd frontend && npx playwright test
# Tests: tests/e2e/upload-flow.spec.ts
```

---

## 21. Deployment Steps

### Quick Deploy (15 Minutes)

```
STEP 1: Clone and install
─────────────────────────
git clone <your-repo>
cd frontend && npm install

STEP 2: Login to Convex
─────────────────────────
npx convex login    → Opens browser for GitHub auth

STEP 3: Deploy to Convex
─────────────────────────
npx convex deploy   → Pushes all backend functions to Convex Cloud

STEP 4: Deploy to Vercel
─────────────────────────
Option A: vercel --prod (from frontend/)
Option B: vercel.com/new → Import GitHub repo

STEP 5: Add environment variables in Vercel
─────────────────────────────────────────────
NEXT_PUBLIC_CONVEX_URL = https://YOUR-PROJECT.convex.cloud
OPENROUTER_API_KEY     = sk-or-v1-YOUR-KEY
GROQ_API_KEY           = gsk_YOUR-KEY        (Optional)

STEP 6: Verify
────────────────
Open https://autoinsight-ai.vercel.app
→ Register account → Login → Upload CSV → See reports
```

---

## 22. File Tree (Complete)

```
autoinsight-ai/
│
├── DEPLOYMENT.md                          ← Deployment guide
├── FINAL_PROJECT_REPORT.md                ← Final project report
├── FINAL_TESTING_REPORT.md                ← Testing report (NEW)
├── MARKET_DEPLOYMENT_GUIDE.md             ← Market deployment guide (NEW)
├── COMPLETE_TECHNICAL_REPORT.md           ← This technical report (NEW)
│
├── README.md                              ← Project overview
├── requirements.txt                       ← Python dependencies (local dev)
├── nginx.conf                             ← Nginx config (local dev)
├── prometheus.yml                         ← Monitoring config (local dev)
├── docker-compose.yml                     ← Docker setup (local dev)
├── Dockerfile                             ← Docker image (local dev)
│
├── .github/workflows/
│   └── ci-cd.yml                          ← CI/CD pipeline
│
├── frontend/                              ← MAIN DEPLOYMENT TARGET
│   ├── package.json                       ← Dependencies
│   ├── next.config.js                     ← Next.js + Convex config
│   ├── tsconfig.json                      ← TypeScript config
│   ├── tailwind.config.ts                 ← Tailwind CSS theme
│   ├── postcss.config.js                  ← PostCSS config
│   ├── vitest.config.ts                   ← Test config
│   ├── .env.example                       ← Environment variables template
│   │
│   ├── convex/                            ← DEPLOYS TO CONVEX CLOUD
│   │   ├── convex.json                    ← Convex project config
│   │   ├── schema.ts                      ← 9 database tables
│   │   ├── auth.config.ts                 ← Auth providers
│   │   ├── users.ts                       ← User CRUD
│   │   ├── uploads.ts                     ← File upload
│   │   ├── datasets.ts                    ← Data storage
│   │   ├── nlq.ts                         ← NLQ chat
│   │   ├── reports.ts                     ← Report engine + exports
│   │   ├── dashboards.ts                  ← Dashboard gen
│   │   ├── audit.ts                       ← Audit log
│   │   ├── pipeline/
│   │   │   ├── index.ts                   ← Orchestrator
│   │   │   ├── stage1.ts                  ← Schema inference
│   │   │   ├── stage2.ts                  ← Clean + PII
│   │   │   ├── stage3.ts                  ← LangGraph
│   │   │   └── stage4.ts                  ← Column engine
│   │   └── lib/
│   │       ├── openrouter.ts              ← LLM client (PRIMARY)
│   │       ├── groq.ts                    ← DEPRECATED
│   │       └── export_templates.ts        ← Export templates
│   │
│   ├── public/
│   │   ├── manifest.json                  ← PWA manifest
│   │   └── sw.js                          ← Service worker
│   │
│   └── src/
│       ├── app/
│       │   ├── page.tsx                   ← Home/redirect
│       │   ├── layout.tsx                 ← Root layout (PWA metadata)
│       │   ├── providers.tsx              ← Convex + Query + Auth
│       │   ├── globals.css               ← Global styles
│       │   ├── upload/page.tsx            ← File upload
│       │   ├── dashboard/page.tsx         ← Dashboard
│       │   ├── reports/[id]/page.tsx      ← Report viewer
│       │   ├── nlq/page.tsx               ← NLQ chat
│       │   ├── admin/page.tsx             ← Admin panel
│       │   ├── system/page.tsx            ← System status
│       │   ├── auth/login/page.tsx        ← Login
│       │   ├── auth/register/page.tsx     ← Register
│       │   └── offline/page.tsx           ← PWA offline
│       │
│       ├── components/
│       │   ├── ChartWidget.tsx            ← Interactive charts
│       │   ├── DashboardGrid.tsx          ← Grid layout
│       │   ├── FilterBar.tsx              ← Filters
│       │   ├── Layout.tsx                 ← App layout
│       │   ├── RequireAuth.tsx            ← Auth guard
│       │   └── ReportExport.tsx           ← Export buttons
│       │
│       ├── context/
│       │   └── AuthContext.tsx            ← Auth state
│       │
│       ├── lib/
│       │   ├── api.ts                     ← API client (for local backend)
│       │   ├── utils.ts                   ← Utility functions
│       │   └── utils.test.ts             ← Unit tests (21 tests)
│       │
│       ├── store/
│       │   └── index.ts                   ← Zustand store
│       │
│       └── types/
│           └── index.ts                   ← TypeScript types
│
└── backend/                               ← LOCAL DEV ONLY
    ├── api.py                             ← FastAPI endpoints
    ├── auth.py                            ← Auth logic
    ├── config.py                          ← Configuration
    ├── database.py                        ← Database connection
    ├── schemas.py                         ← Pydantic models
    ├── pipeline/                          ← Python pipeline
    ├── report/                            ← Python reports
    ├── nlq/                               ← Python NLQ
    └── tests/                             ← Python tests
```

---

## 📋 Quick Reference Card

### Important Commands

```bash
# Frontend
cd frontend
npm install              # Install dependencies
npm run dev              # Start dev server (localhost:3000)
npm run build            # Build for production
npx convex dev           # Start Convex dev environment
npx convex deploy        # Deploy to Convex Cloud
npx vitest run           # Run tests
npx tsc --noEmit         # TypeScript check

# Deployment
npx convex login         # Login to Convex
npx convex deploy-key    # Generate deploy key for CI/CD
vercel --prod            # Deploy to Vercel

# Git
git add .
git commit -m "message"
git push                 # Triggers CI/CD pipeline
```

### Important URLs

| Resource | URL |
|----------|-----|
| **App (Vercel)** | `https://autoinsight-ai.vercel.app` |
| **Convex Dashboard** | `https://dashboard.convex.dev` |
| **OpenRouter Keys** | `https://openrouter.ai/keys` |
| **Groq Console** | `https://console.groq.com/keys` |
| **GitHub Repo** | `https://github.com/YOUR_USERNAME/autoinsight-ai` |

---

## ✅ Final Verification Checklist

After reading this report, you should be able to answer:

- [x] How many database tables exist? → **9**
- [x] What are they? → **users, uploads, pipelineResults, reports, dashboards, conversations, datasets, auditLog, prompts**
- [x] How many frontend pages? → **9 pages + 1 offline fallback**
- [x] How many pipeline stages? → **4 stages** (Schema → Clean → LangGraph → Column)
- [x] How many report agents? → **8 agents** (Business Understanding, Data Overview, Data Quality, EDA, Statistical Analysis, Visualization, Key Observations, Recommendations)
- [x] What LLM is used? → **OpenRouter** (qwen/qwen3-coder:free)
- [x] What is the fallback? → **OpenRouter** (llama-4-maverick:free) → **Groq** (llama-3.3-70b)
- [x] How many export formats? → **4** (HTML, Markdown, PDF, Excel)
- [x] Where is the app hosted? → **Vercel** (frontend) + **Convex Cloud** (backend)
- [x] Is it device-independent? → **Yes** — any device, any browser, anywhere
- [x] What is the operating cost? → **$0/month**
- [x] How many tests pass? → **21 tests, all passing**
- [x] How to deploy? → **4 commands** (convex login → convex deploy → vercel deploy → add env vars)
