# =============================================================================
# REPORT 1: AUTOINSIGHT AI — COMPLETE TECHNICAL ARCHITECTURE REPORT
# =============================================================================
# Covers V1 through V5 — Full System Design, Flow Charts, Component Details
# =============================================================================

## 📋 TABLE OF CONTENTS
1. [System Overview](#1-system-overview)
2. [V1.0 — Core Pipeline Architecture](#2-v10--core-pipeline-architecture)
3. [V2 — Chart Builder & Email Scheduling](#3-v2--chart-builder--email-scheduling)
4. [V3 — Python ML Microservice](#4-v3--python-ml-microservice)
5. [V4 — Multi-Dataset Joins Engine](#5-v4--multi-dataset-joins-engine)
6. [V5 — Enterprise SSO & NL Report Editing](#6-v5--enterprise-sso--nl-report-editing)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Backend Architecture](#8-backend-architecture)
9. [Complete File Map](#9-complete-file-map)
10. [Technology Stack Summary](#10-technology-stack-summary)

---

## 1. SYSTEM OVERVIEW

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER (Browser/CLI)                           │
└──────────────────┬──────────────────────────────────────┬───────────┘
                   │                                      │
                   ▼                                      ▼
┌──────────────────────────────┐       ┌──────────────────────────────┐
│     NEXT.JS FRONTEND (Vercel) │       │    FASTAPI BACKEND (Docker)  │
│                              │       │                              │
│  ┌────────────────────────┐  │       │  ┌────────────────────────┐  │
│  │  Auth Pages            │  │       │  │  Pipeline Orchestrator │  │
│  │  - /auth/login (V5)    │  │       │  │  ├─ Stage 1: CSV→JSON │  │
│  │  - /auth/register      │  │       │  │  ├─ Stage 2: Cleaning  │  │
│  │                        │  │       │  │  ├─ Stage 3: LangGraph │  │
│  │  Dashboard Pages       │  │       │  │  └─ Stage 4: Col Eng   │  │
│  │  - /dashboard          │  │       │  │                        │  │
│  │  - /dashboard/builder  │  │  HTTP │  │  Report Engine         │  │
│  │  - /upload             │  │◄─────►│  │  ├─ Phase 1: Profiling │  │
│  │                        │  │       │  │  ├─ Phase 2: SubAgents │  │
│  │  Data Pages            │  │       │  │  ├─ Phase 3: Validate  │  │
│  │  - /data/joins (V4)    │  │       │  │  └─ Phase 4: Export    │  │
│  │  - /data/ml (V3 UI)    │  │       │  │                        │  │
│  │                        │  │       │  │  NLQ Engine            │  │
│  │  Report Pages          │  │       │  │  ├─ SQL Generation     │  │
│  │  - /reports            │  │       │  │  └─ Response Synthesis │  │
│  │  - /reports/[id] (V5)  │  │       │  └────────────────────────┘  │
│  │                        │  │       └────────┬──────────────────────┘
│  │  NLQ Chat              │  │                │
│  │  - /nlq                │  │       ┌────────▼──────────────────────┐
│  └────────────────────────┘  │       │     INFRASTRUCTURE LAYER      │
│                              │       │                              │
│  ┌────────────────────────┐  │       │  ┌──────────┐ ┌──────────┐  │
│  │  CONVEX BACKEND (SaaS) │  │       │  │PostgreSQL│ │  Redis   │  │
│  │  (Serverless DB+Funcs) │◄─┤       │  │   (15)   │ │   (7)    │  │
│  │                        │  │       │  └──────────┘ └──────────┘  │
│  │  convex/schema.ts      │  │       │  ┌──────────┐ ┌──────────┐  │
│  │  convex/reports.ts     │  │       │  │  MinIO   │ │ Celery   │  │
│  │  convex/joins.ts (V4)  │  │       │  │  (S3)    │ │ (Worker) │  │
│  │  convex/nlq.ts         │  │       │  └──────────┘ └──────────┘  │
│  │  convex/pipeline/      │  │       │                              │
│  │  convex/users.ts       │  │       │  ┌────────────────────────┐  │
│  │  convex/audit.ts       │  │       │  │  ML SERVICE (Railway)  │  │
│  │  convex/dashboards.ts  │  │       │  │  FastAPI+PyCaret+SHAP  │  │
│  │  convex/datasets.ts    │  │  HTTP │  │  /health, /train,      │  │
│  │  convex/uploads.ts     │  │◄─────►│  │  /predict-and-explain  │  │
│  └────────────────────────┘  │       │  └────────────────────────┘  │
│                              │       └──────────────────────────────┘
└──────────────────────────────┘
```

### 1.2 Data Flow Overview

```
User Uploads CSV
       │
       ▼
┌──────────────────────────────────────────────┐
│            CONVEX PIPELINE (4 Stages)         │
│                                               │
│  Stage 1: Schema Inference                    │
│  ├─ Reads CSV sample (100 rows)               │
│  ├─ Calls OpenRouter (Qwen 2.5 72B)           │
│  └─ Outputs: SchemaInferenceResponse           │
│                                               │
│  Stage 2: Data Cleaning                       │
│  ├─ Profiles data quality                     │
│  ├─ Generates cleaning plan via OpenRouter    │
│  └─ Outputs: Cleaned Data + QualityProfile    │
│                                               │
│  Stage 3: LangGraph Agent                     │
│  ├─ 4-node workflow (profile→reason→act→eval) │
│  ├─ Discovers column relationships            │
│  └─ Outputs: UnifiedDataModel (partial)       │
│                                               │
│  Stage 4: Column Engineering                  │
│  ├─ Safe AST-sandboxed Polars eval            │
│  ├─ Generates visualization schema            │
│  └─ Outputs: Complete UnifiedDataModel        │
│                                               │
│  Stored in: datasets table + pipelineResults  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         CONVEX REPORT ENGINE (4 Phases)       │
│                                               │
│  Phase 1: Data Profiling (zero LLM)          │
│  ├─ schema_metadata, univariate_stats         │
│  ├─ bivariate_matrix, trends                  │
│  └─ 5 deterministic Polars functions          │
│                                               │
│  Phase 2: 8 Parallel Sub-Agents (OpenRouter) │
│  ├─ Business Understanding                    │
│  ├─ Data Collection                           │
│  ├─ Cleaning Analysis                         │
│  ├─ Exploratory Data Analysis                 │
│  ├─ Statistical Analysis                      │
│  ├─ Dashboard Visualization                   │
│  ├─ Insights                                  │
│  └─ Recommendations                           │
│                                               │
│  Phase 3: Validation                          │
│  ├─ Pydantic schema compliance                │
│  ├─ Confidence gating (≥0.65 threshold)       │
│  └─ Retry with temperature escalation         │
│                                               │
│  Phase 4: Export                              │
│  ├─ HTML (Jinja2)                             │
│  ├─ Markdown (template)                       │
│  ├─ PDF (@react-pdf/renderer)                 │
│  └─ XLSX (xlsx library)                       │
│                                               │
│  Stored in: reports table                     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         DOWNSTREAM CONSUMERS (V2-V5)          │
│                                               │
│  NLQ Chat: Natural language → SQL → results   │
│  ├─ Intent parsing via OpenRouter             │
│  ├─ In-memory SQL execution                   │
│  └─ Response synthesis                        │
│                                               │
│  V2 Chart Builder: Drag-drop dashboards       │
│  ├─ react-grid-layout grid                    │
│  ├─ recharts visualizations                   │
│  └─ Convex data queries                       │
│                                               │
│  V3 ML Service: AutoML predictions            │
│  ├─ PyCaret AutoML model selection            │
│  ├─ SHAP feature importance                   │
│  └─ API: /predict-and-explain                 │
│                                               │
│  V4 Joins: Multi-dataset relationships        │
│  ├─ Index-based join engine                   │
│  ├─ inner/left/right/outer joins              │
│  └─ Cached in joinedDatasets table            │
│                                               │
│  V5 Report Editor: NL edit + live preview     │
│  ├─ react-markdown rendering                  │
│  ├─ AI Improve via OpenRouter                 │
│  └─ Save title + content                      │
└──────────────────────────────────────────────┘
```

---

## 2. V1.0 — CORE PIPELINE ARCHITECTURE

### 2.1 4-Stage Pipeline Flow Chart

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PIPELINE ORCHESTRATOR                              │
│                    (convex/pipeline/index.ts)                           │
│                                                                         │
│  Input: uploadId, datasetId, userId, skipCleaning?                      │
│                                                                         │
│  ┌────────────────┐                                                     │
│  │  Init Pipeline  │  Create pipelineResults record                     │
│  └────────┬───────┘                                                     │
│           ▼                                                             │
│  ┌────────────────┐     ┌──────────────────────────────┐                │
│  │  STAGE 1       │────▶│  Schema Inference            │                │
│  │  Schema Infer  │     │  - Read 100 sample rows      │                │
│  │  (convex/      │     │  - Call OpenRouter API        │                │
│  │  pipeline/     │     │  - Return column types        │                │
│  │  stage1.ts)    │     └──────────────────────────────┘                │
│  └────────┬───────┘                                                     │
│           ▼                                                             │
│  ┌────────────────┐     ┌──────────────────────────────┐                │
│  │  STAGE 2       │────▶│  Data Cleaning                │                │
│  │  Data Clean    │     │  - Profile data quality        │                │
│  │  (convex/      │     │  - Generate cleaning plan      │                │
│  │  pipeline/     │     │  - Apply transformations       │                │
│  │  stage2.ts)    │     │  - skipCleaning bypass         │                │
│  │  [SKIPPABLE]   │     └──────────────────────────────┘                │
│  └────────┬───────┘                                                     │
│           ▼                                                             │
│  ┌────────────────┐     ┌──────────────────────────────┐                │
│  │  STAGE 3       │────▶│  LangGraph Agent              │                │
│  │  LangGraph     │     │  - 4-node workflow             │                │
│  │  (convex/      │     │  - Profile → Reason → Act→Eval │                │
│  │  pipeline/     │     │  - Discovers relationships    │                │
│  │  stage3.ts)    │     │  - Generates derived columns  │                │
│  │  [LLM HEAVY]   │     └──────────────────────────────┘                │
│  └────────┬───────┘                                                     │
│           ▼                                                             │
│  ┌────────────────┐     ┌──────────────────────────────┐                │
│  │  STAGE 4       │────▶│  Column Engineering            │                │
│  │  Column Engine │     │  - Safe Polars eval             │                │
│  │  (convex/      │     │  - Materialize derived cols    │                │
│  │  pipeline/     │     │  - Build viz schema + layout  │                │
│  │  stage4.ts)    │     └──────────────────────────────┘                │
│  └────────┬───────┘                                                     │
│           ▼                                                             │
│  ┌────────────────┐                                                     │
│  │  Complete       │  Save UnifiedDataModel + update upload status      │
│  └────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Confidence Gating System

```
LLM Response
     │
     ▼
┌─────────────────────┐
│  Confidence Score?   │
│  (0.0 - 1.0)        │
└──────┬──────────────┘
       │
       ├──── ≥ 0.90 ──► 🟢 Auto-Apply (Green)
       │
       ├──── ≥ 0.70 ──► 🟡 Manual Approval (Yellow)
       │
       ├──── ≥ 0.50 ──► 🟠 Review Required (Orange)
       │
       └──── < 0.50 ──► 🔴 Advisory Only (Red)
                            │
                            ▼
                    ┌─────────────────┐
                    │  Retry (max 3)  │
                    │  Temp: 0.1→0.5  │
                    └────────┬────────┘
                             │
                      ┌──────▼──────┐
                      │  Fallback    │
                      │  (Determin-  │
                      │  istic)      │
                      └─────────────┘
```

### 2.3 Report Engine 4-Phase Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      REPORT ENGINE (convex/reports.ts)                   │
│                                                                         │
│  Phase 1: Data Profiling (Zero LLM Cost)                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  buildDataProfile(): Extract metadata from dataset               │   │
│  │  - columnCount, rowCount, numericColumns, categoricalColumns     │   │
│  │  - Column names, types, relationships count, derived cols       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  Phase 2: 8 Parallel Sub-Agents (OpenRouter Qwen 2.5 72B)              │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  AGENT_TYPES = [                                                   │   │
│  │    "business_understanding",  ← Business context & goals         │   │
│  │    "data_collection",         ← Data sourcing & profiling        │   │
│  │    "cleaning_analysis",       ← Data quality assessment          │   │
│  │    "eda",                     ← Exploratory analysis             │   │
│  │    "statistical_analysis",    ← Statistical deep dive            │   │
│  │    "dashboard_viz",           ← Visualization recommendations    │   │
│  │    "insights",                ← Key findings                     │   │
│  │    "recommendations",         ← Actionable recommendations       │   │
│  │  ]                                                                │   │
│  │                                                                      │   │
│  │  All 8 agents run via Promise.all() — fully parallel               │   │
│  │  Each agent: retry up to 3× with temp escalation (0.1→0.3→0.5)   │   │
│  │  Confidence gate: ≥ 0.65 threshold                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  Phase 3: Validation                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Pydantic schema compliance check                               │   │
│  │  Confidence gating (≥0.65)                                       │   │
│  │  Fallback generation for failed agents                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  Phase 4: Export                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  exportReport(): Action supporting:                              │   │
│  │  - "html"     → Jinja2 template → generateHtmlExport()           │   │
│  │  - "markdown" → Markdown template → generateMarkdownExport()     │   │
│  │  - "pdf"      → @react-pdf/renderer (client-side)               │   │
│  │  - "excel"    → xlsx library (client-side)                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.4 NLQ Chat Architecture

```
User Question: "Show me total sales by region"
       │
       ▼
┌──────────────────────────────────────────────┐
│  NLQ ACTION (convex/nlq.ts)                   │
│                                               │
│  Step 1: Intent Parsing                       │
│  ├─ Get dataset schema from datasets table     │
│  ├─ Build schemaInfo (columns + sample values) │
│  ├─ Call OpenRouter with NLQ_SYSTEM_PROMPT    │
│  └─ Returns: metrics, dimensions, SQL, conf   │
│                                               │
│  Step 2: Execute Query                        │
│  ├─ Parse SQL for GROUP BY, aggregates        │
│  ├─ In-memory execution on dataset.data        │
│  └─ Returns: filtered/aggregated results       │
│                                               │
│  Step 3: Response Synthesis                   │
│  ├─ Call OpenRouter with NLQ_RESPONSE_PROMPT  │
│  ├─ Generate natural language answer          │
│  └─ Optional: chart config for visualization   │
│                                               │
│  Stored in: conversations table (max 20 msgs) │
└──────────────────────────────────────────────┘
```

---

## 3. V2 — CHART BUILDER & EMAIL SCHEDULING

### 3.1 Chart Builder Component Tree

```
dashboard/builder/page.tsx
│
├── ConvexChartBuilder (loads real Convex data)
│   ├── useQuery(api.datasets.getDatasetByUpload, { uploadId })
│   ├── WidgetCard × N (one per chart widget)
│   │   ├── react-grid-layout (draggable, resizable)
│   │   ├── input (title editing)
│   │   └── ChartRenderer
│   │       ├── BarChart (recharts)
│   │       ├── LineChart (recharts)
│   │       ├── PieChart (recharts)
│   │       ├── AreaChart (recharts)
│   │       ├── ScatterChart (recharts)
│   │       └── BarChart stacked (recharts)
│   │
│   └── ChartPalette (sidebar with chart type buttons)
│       ├── Bar, Line, Pie, Area, Scatter, Stacked
│       └── onClick → handleAddChart(type)
│
├── Controls
│   ├── Upload selector (dropdown of user uploads)
│   ├── Add Chart button
│   └── Save Layout button
│
└── ReportExport (email scheduling)
    ├── Frequency selector (daily/weekly/monthly)
    ├── Email input
    ├── Schedule button
    └── localStorage persistence
```

### 3.2 Package Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react-grid-layout | ^2.2.3 | Drag-and-drop responsive grid |
| recharts | ^3.8.1 | React charting (SVG-based) |
| react-markdown | ^9.0.0 | Markdown rendering for reports |
| resend | ^6.12.4 | Email sending (scheduled reports) |
| react-hot-toast | ^2.4.0 | Toast notifications |

---

## 4. V3 — PYTHON ML MICROSERVICE

### 4.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   ML MICROSERVICE (Railway/Render)                   │
│                                                                     │
│  ┌──────────────────────┐    ┌────────────────────────────────┐     │
│  │     Dockerfile        │    │    main.py (FastAPI)           │     │
│  │  python:3.10-slim    │    │                                │     │
│  │  pip install -r reqs │    │  GET  /health                  │     │
│  │  CMD uvicorn main    │    │  POST /train                   │     │
│  └──────────────────────┘    │  POST /predict-and-explain     │     │
│                               │  GET  /model-info              │     │
│  ┌──────────────────────┐    └────────────────────────────────┘     │
│  │  requirements.txt    │                                           │
│  │  fastapi==0.109.0    │    ┌────────────────────────────────┐     │
│  │  pycaret==3.2.0     │    │    Model Cache (joblib)          │     │
│  │  shap==0.44.0       │    │    models/                      │     │
│  │  xgboost==2.0.3     │    │    ├── best_model.pkl           │     │
│  │  scikit-learn==1.4.0│    │    └── model_meta.pkl           │     │
│  └──────────────────────┘    └────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
         ▲                                        │
         │              HTTP POST                 │
         │         /predict-and-explain           │
         │                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVEX INTEGRATION                                │
│  convex/reports.ts :: runMlAnalysis(datasetId, reportId)            │
│                                                                     │
│  1. Fetch dataset from Convex                                       │
│  2. Check ML service health → /health                               │
│  3. Send data → /predict-and-explain { data: dataset.slice(0,1000)} │
│  4. Receive { best_model, predictions, feature_importance }         │
│  5. Generate ML section content (table format)                      │
│  6. Append to existing report sections                              │
│  7. Save updated report                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 ML Pipeline Flow

```
User Request
     │
     ▼
┌─────────────────┐
│  Check Health    │──── GET /health
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Load Data       │
│  from Convex     │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  POST /predict-and-explain                    │
│                                               │
│  ┌────────────────────────────────────────┐  │
│  │  1. Convert JSON → Pandas DataFrame     │  │
│  │  2. Try loading cached model (joblib)   │  │
│  │  3. If no cache:                        │  │
│  │     a. PyCaret setup(data, target)      │  │
│  │     b. compare_models(n_select=1)       │  │
│  │     c. Cache model to disk              │  │
│  │  4. pyc.predict_model(model, data)      │  │
│  │  5. SHAP TreeExplainer → feature_importance│
│  │  6. Return JSON response                │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  ML Section      │
│  Appended to     │
│  Report          │
└─────────────────┘
```

---

## 5. V4 — MULTI-DATASET JOINS ENGINE

### 5.1 Join Engine Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      JOIN ENGINE (convex/joins.ts)                       │
│                                                                         │
│  Tables:                                                                 │
│  ┌────────────────────┐    ┌─────────────────────┐                     │
│  │ datasetRelations   │    │ joinedDatasets      │                     │
│  │ - sourceUploadId   │    │ - relationId        │                     │
│  │ - targetUploadId   │    │ - columns           │                     │
│  │ - sourceColumn     │    │ - rowCount          │                     │
│  │ - targetColumn     │    │ - data (cached)     │                     │
│  │ - joinType         │    └─────────────────────┘                     │
│  │   inner|left|right|outer│                                          │
│  └────────────────────┘                                                │
│                                                                         │
│  Mutations:                                                             │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │ createRelation(userId, name, sourceUploadId, targetUploadId,   │    │
│  │                sourceColumn, targetColumn, joinType)           │    │
│  │                                                                │    │
│  │ deleteRelation(relationId)  ← Also cleans cached joined data  │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Action: executeJoin(relationId, userId)                                │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  1. Fetch relation from datasetRelations                        │    │
│  │  2. Fetch source + target datasets from datasets table          │    │
│  │  3. Build index: Map<key, rows[]> from target dataset           │    │
│  │  4. For each source row:                                       │    │
│  │     a. Lookup key in target index                              │    │
│  │     b. Join based on type:                                     │    │
│  │        - INNER: only matched rows                               │    │
│  │        - LEFT: all source + null targets                       │    │
│  │        - RIGHT: all target + null sources                      │    │
│  │        - OUTER: all rows from both                             │    │
│  │     c. Prefix columns: source_col, target_col                  │    │
│  │  5. Cache result in joinedDatasets                              │    │
│  │  6. Return { columns, rowCount, data(100 preview) }            │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Join Type Behavior

```
INNER JOIN:
  Source: [1, 2, 3]  Target: [2, 3, 4]
  Result: [(2, matched), (3, matched)]
  
LEFT JOIN:
  Source: [1, 2, 3]  Target: [2, 3, 4]
  Result: [(1, null), (2, matched), (3, matched)]

RIGHT JOIN:
  Source: [1, 2, 3]  Target: [2, 3, 4]
  Result: [(2, matched), (3, matched), (null, 4)]

OUTER JOIN:
  Source: [1, 2, 3]  Target: [2, 3, 4]
  Result: [(1, null), (2, matched), (3, matched), (null, 4)]
```

---

## 6. V5 — ENTERPRISE SSO & NL REPORT EDITING

### 6.1 Enterprise SSO Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATION SYSTEM                           │
│                                                                     │
│  V5a: OAuth Providers (convex/auth.config.ts)                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  providers: [                                                   │  │
│  │    { domain: "https://accounts.google.com",                    │  │
│  │      applicationID: "" ← GOOGLE_CLIENT_ID env var }           │  │
│  │    { domain: "https://github.com/login/oauth",                 │  │
│  │      applicationID: "" ← GITHUB_CLIENT_ID env var }           │  │
│  │    { domain: "https://your-tenant.us.auth0.com",  ← SAML     │  │
│  │      applicationID: "auth0_saml_client_id" }                   │  │
│  │    { domain: "https://your-org.okta.com/oauth2/default",       │  │
│  │      applicationID: "okta_sso_client_id" }                     │  │
│  │  ]                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Login Page: src/app/auth/login/page.tsx                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  - Email/Password form (existing)                             │  │
│  │  - Google OAuth button ← uses Convex Auth                    │  │
│  │  - GitHub OAuth button ← uses Convex Auth                    │  │
│  │  - Toast notification for env var setup                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 NL Report Editing Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              REPORT VIEWER (src/app/reports/[id]/page.tsx)           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  State: editingIndex (null = viewing, n = editing section n)  │  │
│  │  State: editContent, editTitle                                 │  │
│  │                                                                  │  │
│  │  View Mode:                                                     │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  <ReactMarkdown> ← Renders section.content               │  │  │
│  │  │  <remark-gfm> ← GitHub Flavored Markdown support         │  │  │
│  │  │  <rehype-highlight> ← Code syntax highlighting           │  │  │
│  │  │  Edit button per section                                  │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  │                                                                  │  │
│  │  Edit Mode:                                                     │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  Textarea with section content                           │  │  │
│  │  │  Live Markdown preview (split pane)                      │  │  │
│  │  │  "AI Improve" button:                                    │  │  │
│  │  │    ├─ Calls OpenRouter with edit instructions             │  │  │
│  │  │    └─ Replaces content with AI-enhanced version           │  │  │
│  │  │  Save / Cancel buttons                                    │  │  │
│  │  │  Title editing: editTitle state                           │  │  │
│  │  │  Saves via updateSingleReportSection mutation             │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. FRONTEND ARCHITECTURE

### 7.1 Next.js App Router Structure

```
src/app/
├── layout.tsx          ← Root layout (Inter font, Providers, globals.css)
├── page.tsx            ← Redirects to /dashboard or /auth/login
├── providers.tsx       ← ConvexProvider + QueryClientProvider + AuthProvider
├── globals.css         ← Tailwind CSS + custom styles
│
├── auth/
│   ├── login/page.tsx  ← Email/password + V5 Google/GitHub OAuth
│   └── register/page.tsx
│
├── dashboard/
│   ├── page.tsx        ← Dashboard grid + chart queries
│   └── builder/page.tsx ← V2 Chart Builder page
│
├── upload/page.tsx     ← CSV file upload with dropzone
├── nlq/page.tsx        ← Natural language query chat
├── reports/
│   ├── page.tsx        ← Reports list
│   └── [id]/page.tsx   ← V5 Report viewer with editing
├── admin/page.tsx      ← Admin panel
├── system/page.tsx     ← System monitoring
├── data/
│   ├── joins/page.tsx  ← V4 Data joins UI
│   └── ml/page.tsx     ← V3 ML analysis UI
└── offline/page.tsx    ← Offline support
```

### 7.2 Component Hierarchy

```
Layout.tsx (Navigation Sidebar)
├── Home
├── Dashboard
├── Chart Builder (V2)
├── Upload Data
├── Reports
├── NLQ Chat
├── Data Joins (V4)
├── ML Analysis (V3)
├── Admin
└── System

Layout wraps:
├── RequireAuth (auth guard)
└── {children} (page content)

Per-page components:
├── ChartWidget.tsx       ← Reusable chart rendering
├── ChartBuilder.tsx      ← V2 drag-drop grid (react-grid-layout)
├── ConvexChartBuilder.tsx ← V2 real data version
├── ChartPalette.tsx      ← V2 chart type selector
├── DashboardGrid.tsx     ← Dashboard layout grid
├── FilterBar.tsx         ← Data filtering
├── ReportExport.tsx      ← V2 email scheduling
└── DragHandle            ← Widget drag handle
```

### 7.3 State Management

```
Context (React Context):
├── AuthContext.tsx
│   ├── user: Doc<"users"> | null
│   ├── isAuthenticated: boolean
│   ├── isLoading: boolean
│   ├── login(email, password)
│   ├── register(name, email, password)
│   ├── logout()
│   └── refreshUser()

Store (Zustand — src/store/index.ts):
├── uploadStore (upload progress)
├── pipelineStore (pipeline status)
└── chartStore (chart builder state)

Convex Queries (Reactive):
├── useQuery(api.users.getUser, ...)
├── useQuery(api.uploads.listUploads, ...)
├── useQuery(api.datasets.getDataset, ...)
├── useQuery(api.datasets.getDatasetByUpload, ...)
├── useQuery(api.reports.listReports, ...)
├── useQuery(api.joins.listRelations, ...)
├── useQuery(api.joins.listJoinedDatasets, ...)
└── useQuery(api.audit.listAuditLogs, ...)

Convex Mutations:
├── useMutation(api.users.createUser)
├── useMutation(api.uploads.initiateUpload)
├── useMutation(api.datasets.storeDataset)
├── useMutation(api.reports.initReport)
├── useMutation(api.joins.createRelation)
├── useMutation(api.joins.deleteRelation)
└── useMutation(api.audit.logAction)

Convex Actions:
├── useAction(api.reports.generateReport)
├── useAction(api.reports.exportReport)
├── useAction(api.reports.runMlAnalysis)
├── useAction(api.reports.editReportSection)
├── useAction(api.pipeline.runPipeline)
├── useAction(api.joins.executeJoin)
└── useAction(api.nlq.query)
```

---

## 8. BACKEND ARCHITECTURE

### 8.1 FastAPI Backend Structure

```
backend/
├── api.py                ← Main FastAPI app (routes, middleware, lifespan)
├── config.py             ← Pydantic Settings (env vars, validation)
├── database.py           ← asyncpg connection pool + CRUD utilities
├── schemas.py            ← All Pydantic v2 models (data contracts)
├── auth.py               ← JWT token creation/verification + password hashing
├── cache.py              ← Redis cache manager
├── storage.py            ← S3/MinIO file storage
├── tools.py              ← Data processing tools (Polars, profiling)
├── tasks.py              ← Celery async task definitions
├── upload.py             ← Chunked file upload handler
├── prompt_registry.py    ← Versioned LLM prompt templates
│
├── middleware/
│   ├── __init__.py
│   ├── auth.py           ← JWT auth middleware + request logging
│   ├── performance.py    ← Request timing, cache headers
│   ├── security.py       ← SQL injection detection, rate limiting
│   └── register.py       ← Middleware registration
│
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py   ← Pipeline controller (retry, progress, state)
│   ├── progress.py       ← Progress tracking + SSE events
│   ├── stage1_csv_to_json.py    ← Schema inference
│   ├── stage2_data_clean.py     ← Data cleaning
│   ├── stage3_langgraph_agent.py ← LangGraph relationship discovery
│   └── stage4_column_engine.py  ← Column engineering
│
├── nlq/
│   ├── __init__.py
│   ├── chat.py           ← NLQ chat processing
│   └── dashboard.py      ← Dashboard viz schema generation
│
└── report/
    ├── __init__.py
    ├── orchestrator.py   ← Report controller
    ├── phase1_profiling.py  ← Deterministic profiling
    ├── phase2_sub_agents.py ← 8 parallel LLM agents
    ├── phase3_validation.py ← Validation + confidence gating
    ├── phase4_export.py     ← Multi-format export
    └── templates/
        ├── report_html.jinja2
        └── report_markdown.jinja2
```

### 8.2 API Endpoints Summary

```
System:
  GET  /health                    — System health check
  GET  /health/ready              — Readiness probe
  GET  /health/live               — Liveness probe
  GET  /api/v1/system/info        — System information

Authentication:
  POST /api/v1/auth/login         — User login (JWT)
  POST /api/v1/auth/register      — User registration
  POST /api/v1/auth/refresh       — Refresh access token

Upload:
  POST /api/v1/upload/initiate    — Start chunked upload
  POST /api/v1/upload/chunk       — Upload file chunk
  POST /api/v1/upload/complete    — Finalize upload
  DELETE /api/v1/upload/{id}      — Cancel upload
  GET  /api/v1/upload/progress/{id} — SSE upload progress

Pipeline:
  POST /api/v1/pipeline/run       — Execute 4-stage pipeline
  GET  /api/v1/pipeline/status/{id} — Pipeline execution status
  GET  /api/v1/pipeline/events/{id} — SSE pipeline events
  GET  /api/v1/pipeline/diff/{id}   — Cleaning diff preview
  POST /api/v1/pipeline/cleaning/approve — Approve cleaning plan

Reports:
  POST /api/v1/reports/generate       — Generate 8-section report
  GET  /api/v1/reports/{id}           — Get report
  GET  /api/v1/reports/{id}/export/{format} — Export (html/md/pdf/xlsx)

NLQ:
  POST /api/v1/nlq/query              — Natural language query

Dashboard:
  GET  /api/v1/dashboard/{id}         — Get dashboard

Admin:
  GET  /api/v1/admin/users            — List users
```

### 8.3 Convex Backend Functions

```
Queries:
  users.getUser(email)                          — Get user by email
  users.getUserById(userId)                     — Get user by ID
  users.listUsers()                             — List all users
  uploads.getUpload(uploadId)                   — Get upload
  uploads.listUploads(userId)                   — List user uploads
  datasets.getDataset(datasetId)                 — Get dataset
  datasets.getDatasetByUpload(uploadId)          — Get dataset by upload
  datasets.listDatasets(userId)                  — List datasets
  reports.getReport(reportId)                   — Get report
  reports.listReports(userId)                   — List reports
  reports.getReportSections(reportId)           — Get sections only
  pipeline.getPipelineResult(pipelineId)        — Get pipeline result
  pipeline.listPipelineResults(userId)          — List pipeline results
  nlq.getConversation(conversationId)           — Get conversation
  nlq.listConversations(userId, uploadId)       — List conversations
  joins.getRelation(relationId)                 — Get relation
  joins.listRelations(userId)                   — List relations
  joins.getJoinedDataset(relationId)            — Get joined result
  joins.listJoinedDatasets(userId)              — List joined datasets
  audit.listAuditLogs(userId?, resourceType?, limit?) — Audit logs
  dashboards.*                                  — Dashboard queries

Mutations:
  users.createUser(email, name, passwordHash, role)
  users.updateUserRole(userId, role)
  users.updateLastLogin(userId)
  users.deleteUser(userId)
  uploads.initiateUpload(userId, fileName, fileSize)
  uploads.updateUploadStatus(uploadId, status, ...)
  uploads.generateUploadUrl()
  datasets.storeDataset(uploadId, userId, columns, rowCount, data)
  datasets.deleteDataset(datasetId)
  reports.initReport(uploadId, userId, title?)
  reports.updateReportSections(reportId, sections, overallConfidence)
  reports.updateSingleReportSection(reportId, sectionType, content)
  pipeline.initPipeline(uploadId, userId)
  pipeline.updatePipelineStage(pipelineId, stageNum, stageName, result)
  pipeline.completePipeline(pipelineId, unifiedDataModel, processingTimeMs)
  pipeline.failPipeline(pipelineId, error)
  nlq.createConversation(userId, uploadId)
  nlq.addMessage(conversationId, role, content, sqlGenerated?, chartConfig?)
  joins.createRelation(...)
  joins.deleteRelation(relationId)
  joins.storeJoinedDataset(...)
  joins.updateJoinedDataset(...)
  audit.logAction(userId, action, resourceType, resourceId?, details?)
  dashboards.* (create, update, delete)

Actions:
  reports.generateReport(uploadId, userId, datasetId, pipelineId, title?)
  reports.exportReport(reportId, format)
  reports.runMlAnalysis(datasetId, reportId) [V3]
  reports.editReportSection(reportId, sectionType, editInstructions) [V5]
  pipeline.runPipeline(uploadId, datasetId, userId, skipCleaning?)
  nlq.query(userId, uploadId, datasetId, conversationId, question)
  joins.executeJoin(relationId, userId) [V4]
```

---

## 9. COMPLETE FILE MAP

```
autoinsight-ai/
│
├── REPORT_1_TECHNICAL_ARCHITECTURE.md    ← THIS REPORT
├── REPORT_2_DEPLOYMENT.md                ← Deployment guide
├── REPORT_3_DATABASE.md                   ← Database schema
│
├── .env.example                          ← Environment variables template
├── .pre-commit-config.yaml               ← Pre-commit hooks
├── .gitignore
│
├── requirements.txt                      ← Python backend dependencies
├── Dockerfile                            ← Backend dev Docker image
├── Dockerfile.prod                       ← Backend prod Docker image
├── docker-compose.yml                    ← Local dev infrastructure
├── docker-compose.prod.yml               ← Production infrastructure
├── nginx.conf                            ← Nginx reverse proxy config
├── prometheus.yml                        ← Prometheus monitoring config
│
├── scripts/
│   └── migrate.py                        ← PostgreSQL schema migration
│
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_pipeline_orchestrator.py
│   ├── test_report_engine.py
│   ├── test_schemas.py
│   ├── test_tools.py
│   └── load/
│       ├── benchmark.py
│       └── locustfile.py
│
├── k8s/
│   └── manifest.yaml                     ← Kubernetes deployment
│
├── .github/workflows/
│   └── ci-cd.yml                         ← GitHub Actions CI/CD
│
├── backend/                              ← [FASTAPI BACKEND]
│   ├── __init__.py
│   ├── api.py
│   ├── auth.py
│   ├── cache.py
│   ├── config.py
│   ├── database.py
│   ├── llm_factory.py
│   ├── prompt_registry.py
│   ├── schemas.py
│   ├── storage.py
│   ├── tasks.py
│   ├── tools.py
│   ├── upload.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── performance.py
│   │   ├── register.py
│   │   └── security.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── progress.py
│   │   ├── stage1_csv_to_json.py
│   │   ├── stage2_data_clean.py
│   │   ├── stage3_langgraph_agent.py
│   │   └── stage4_column_engine.py
│   ├── nlq/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   └── dashboard.py
│   └── report/
│       ├── __init__.py
│       ├── orchestrator.py
│       ├── phase1_profiling.py
│       ├── phase2_sub_agents.py
│       ├── phase3_validation.py
│       ├── phase4_export.py
│       └── templates/
│           ├── report_html.jinja2
│           └── report_markdown.jinja2
│
├── ml-service/                           ← [V3 PYTHON ML MICROSERVICE]
│   ├── requirements.txt
│   ├── main.py
│   └── Dockerfile
│
└── frontend/                             ← [NEXT.JS FRONTEND]
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── tsconfig.json
    ├── vitest.config.ts
    ├── playwright.config.ts
    ├── .gitignore
    ├── convex/
    │   ├── convex.json
    │   ├── auth.config.ts
    │   ├── schema.ts
    │   ├── users.ts
    │   ├── uploads.ts
    │   ├── datasets.ts
    │   ├── reports.ts
    │   ├── nlq.ts
    │   ├── joins.ts                    [V4]
    │   ├── dashboards.ts
    │   ├── audit.ts
    │   ├── scheduled_reports.ts
    │   ├── cross_relations.ts
    │   ├── ml.ts
    │   ├── pipeline/
    │   │   ├── index.ts
    │   │   ├── stage1.ts
    │   │   ├── stage2.ts
    │   │   ├── stage3.ts
    │   │   └── stage4.ts
    │   ├── lib/
    │   │   ├── openrouter.ts
    │   │   ├── prompts.ts
    │   │   ├── csv.ts
    │   │   ├── export_templates.ts
    │   │   └── groq.ts                [DEPRECATED]
    │   └── _generated/
    │       ├── api.js
    │       └── server.js
    │
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx
    │   │   ├── providers.tsx
    │   │   ├── globals.css
    │   │   ├── auth/login/page.tsx    [V5 OAuth buttons]
    │   │   ├── auth/register/page.tsx
    │   │   ├── dashboard/page.tsx
    │   │   ├── dashboard/builder/page.tsx  [V2]
    │   │   ├── upload/page.tsx
    │   │   ├── nlq/page.tsx
    │   │   ├── reports/page.tsx
    │   │   ├── reports/[id]/page.tsx  [V5 NL Editor]
    │   │   ├── admin/page.tsx
    │   │   ├── system/page.tsx
    │   │   ├── data/joins/page.tsx    [V4]
    │   │   ├── data/ml/page.tsx       [V3]
    │   │   └── offline/page.tsx
    │   │
    │   ├── components/
    │   │   ├── Layout.tsx
    │   │   ├── RequireAuth.tsx
    │   │   ├── ChartWidget.tsx
    │   │   ├── ChartBuilder.tsx        [V2]
    │   │   ├── ConvexChartBuilder.tsx  [V2 real data]
    │   │   ├── ChartPalette.tsx        [V2]
    │   │   ├── DashboardGrid.tsx
    │   │   ├── FilterBar.tsx
    │   │   └── ReportExport.tsx
    │   │
    │   ├── context/
    │   │   └── AuthContext.tsx
    │   │
    │   ├── lib/
    │   │   ├── api.ts
    │   │   ├── convex-api.ts
    │   │   ├── utils.ts
    │   │   └── utils.test.ts
    │   │
    │   ├── store/
    │   │   └── index.ts
    │   │
    │   └── types/
    │       └── index.ts
    │
    ├── public/
    │   ├── manifest.json
    │   └── sw.js
    │
    └── tests/
        └── e2e/
            └── upload-flow.spec.ts
```

---

## 10. TECHNOLOGY STACK SUMMARY

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend Framework** | Next.js | ^14.2.0 | React framework with App Router |
| **UI Styling** | Tailwind CSS | ^3.4.0 | Utility-first CSS |
| **Serverless Backend** | Convex | ^1.40.0 | Serverless DB + functions |
| **Backend API** | FastAPI | ≥0.104.0 | Python REST API |
| **Database (Backend)** | PostgreSQL 15 | 15-alpine | Metadata, users, pipelines |
| **Cache** | Redis 7 | 7-alpine | Cache, task queue, SSE state |
| **Task Queue** | Celery | ≥5.3.0 | Async background tasks |
| **File Storage** | MinIO | latest | S3-compatible object storage |
| **Charting** | Recharts | ^3.8.1 | React SVG charts |
| **Grid Layout** | react-grid-layout | ^2.2.3 | Drag-drop dashboard grid |
| **Markdown** | react-markdown | ^9.0.0 | Report rendering |
| **LLM Provider** | OpenRouter (Qwen 2.5 72B) | — | All LLM calls |
| **AutoML (V3)** | PyCaret | ^3.2.0 | Automated ML model selection |
| **ML Explain (V3)** | SHAP | ^0.44.0 | Feature importance |
| **ML Server (V3)** | Uvicorn | ^0.27.0 | ASGI server for FastAPI |
| **CI/CD** | GitHub Actions | — | Automated build + deploy |
| **Orchestration** | Docker Compose | — | Local development |
| **Kubernetes** | k8s manifest | — | Production deployment |
| **Monitoring** | Prometheus | — | Metrics collection |
| **Reverse Proxy** | Nginx | alpine | Load balancing + SSL |

---

*End of Report 1 — Technical Architecture*
