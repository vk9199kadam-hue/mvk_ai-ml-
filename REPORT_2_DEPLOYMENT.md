# =============================================================================
# REPORT 2: AUTOINSIGHT AI — COMPLETE DEPLOYMENT REPORT
# =============================================================================
# Covers Vercel, Convex, Railway, Docker, Kubernetes, CI/CD, Environment Variables
# =============================================================================

## 📋 TABLE OF CONTENTS
1. [Deployment Architecture Overview](#1-deployment-architecture-overview)
2. [Environment Variables Reference](#2-environment-variables-reference)
3. [Vercel Frontend Deployment](#3-vercel-frontend-deployment)
4. [Convex Backend Deployment](#4-convex-backend-deployment)
5. [Railway ML Service Deployment](#5-railway-ml-service-deployment)
6. [Docker Backend Deployment](#6-docker-backend-deployment)
7. [Kubernetes Production Deployment](#7-kubernetes-production-deployment)
8. [CI/CD Pipeline with GitHub Actions](#8-cicd-pipeline-with-github-actions)
9. [Monitoring & Logging](#9-monitoring--logging)
10. [SSL & Security Configuration](#10-ssl--security-configuration)
11. [Domain & DNS Setup](#11-domain--dns-setup)
12. [Cost Estimation](#12-cost-estimation)

---

## 1. DEPLOYMENT ARCHITECTURE OVERVIEW

```
                      ┌──────────────────────┐
                      │    Cloudflare DNS     │
                      │  autoinsight.com      │
                      └──────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐    ┌──────────────────────┐
          │   VERCEL (CDN)   │    │  NGINX (Self-Host)   │
          │   Next.js App    │    │  Proxy + SSL          │
          │   autoinsight.   │    │  api.autoinsight.com  │
          │   vercel.app     │    │                      │
          └────────┬─────────┘    └──────────┬───────────┘
                   │                         │
                   │ HTTP                    │ HTTP
                   ▼                         ▼
          ┌──────────────────┐    ┌──────────────────────┐
          │   CONVEX (SaaS)  │    │   FASTAPI (Docker)   │
          │   Serverless     │    │   api:8000            │
          │   DB + Functions │    │                      │
          │   sleek-herring- │    │  ┌────────────────┐  │
          │   766.convex.cloud│    │  │  PostgreSQL 15 │  │
          └──────────────────┘    │  │  (Docker)      │  │
                                   │  ├────────────────┤  │
          ┌──────────────────┐    │  │  Redis 7       │  │
          │   RAILWAY (PaaS) │    │  │  (Docker)      │  │
          │   ML Service     │◄───┤  ├────────────────┤  │
          │   FastAPI+PyCaret│    │  │  MinIO S3      │  │
          │   ml-service.    │    │  │  (Docker)      │  │
          │   railway.app    │    │  ├────────────────┤  │
          └──────────────────┘    │  │  Celery Worker │  │
                                   │  │  (Docker)      │  │
                                   │  └────────────────┘  │
                                   └──────────────────────┘
```

---

## 2. ENVIRONMENT VARIABLES REFERENCE

### 2.1 Frontend Environment Variables (.env.local)

```bash
# ── Convex (REQUIRED) ──────────────────────────────────────────────────────
NEXT_PUBLIC_CONVEX_URL=https://sleek-herring-766.convex.cloud

# ── Convex Auth OAuth (Required for V5 SSO) ────────────────────────────────
# Get from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Get from: https://github.com/settings/developers
GITHUB_CLIENT_ID=your-github-client-id

# ── Optional ───────────────────────────────────────────────────────────────
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 2.2 Convex Environment Variables (Convex Dashboard)

```bash
# These are set in the Convex Dashboard → Settings → Environment Variables
# Or via CLI: npx convex env set KEY VALUE

# ── LLM Provider (REQUIRED) ────────────────────────────────────────────────
# Get from: https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-api-key

# ── ML Service URL (Optional, defaults to http://localhost:8000) ───────────
# Set to your Railway deployment URL in production
ML_SERVICE_URL=https://ml-service.railway.app

# ── Convex Auth OAuth (Set via Dashboard) ──────────────────────────────────
# These are separate from NEXT_PUBLIC vars — set in Convex Dashboard
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GITHUB_CLIENT_ID=your-github-client-id
```

### 2.3 Backend Environment Variables (.env / .env.production)

```bash
# ── Application Meta ───────────────────────────────────────────────────────
APP_NAME=AutoInsight AI
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=WARNING

# ── Database (PostgreSQL) ──────────────────────────────────────────────────
DATABASE_URL=postgresql://autoinsight:YOUR_DB_PASSWORD@postgres:5432/autoinsight
DB_HOST=postgres
DB_PORT=5432
DB_NAME=autoinsight
DB_USER=autoinsight
DB_PASSWORD=YOUR_SECURE_DB_PASSWORD

# ── Redis (Cache + Task Queue) ─────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# ── S3 File Storage (MinIO) ────────────────────────────────────────────────
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=YOUR_S3_ACCESS_KEY
S3_SECRET_KEY=YOUR_S3_SECRET_KEY
S3_BUCKET=autoinsight-files
S3_REGION=us-east-1
S3_SECURE=false

# ── LLM Provider ───────────────────────────────────────────────────────────
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=qwen-2.5-72b
GROQ_MAX_RETRIES=3
GROQ_TIMEOUT_SECONDS=30

# ── JWT Authentication ─────────────────────────────────────────────────────
JWT_SECRET=your-secure-random-jwt-secret-at-least-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7

# ── Pipeline Configuration ─────────────────────────────────────────────────
MAX_FILE_SIZE_MB=100
PIPELINE_TIMEOUT_SECONDS=300
CHUNK_SIZE_MB=10
PARQUET_COMPRESSION=snappy

# ── CORS ───────────────────────────────────────────────────────────────────
CORS_ORIGINS=https://autoinsight.vercel.app,http://localhost:3000

# ── Celery ─────────────────────────────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# ── Confidence Gating Thresholds ──────────────────────────────────────────
CONFIDENCE_AUTO_APPLY=0.90
CONFIDENCE_MANUAL_APPROVAL=0.70
CONFIDENCE_REVIEW_REQUIRED=0.50
```

### 2.4 ML Service Environment Variables

```bash
# No mandatory env vars needed — all config is in the Dockerfile
# Optional: Set port via uvicorn command in Dockerfile
# Default port: 8000
```

---

## 3. VERCEL FRONTEND DEPLOYMENT

### 3.1 Prerequisites

1. **Vercel Account** — Sign up at https://vercel.com (Free tier available)
2. **GitHub Repository** — Connected to Vercel for automatic deployments
3. **Convex Project** — Already deployed (see Section 4)

### 3.2 Step-by-Step Deployment

```bash
# Step 1: Install Vercel CLI (optional, can also use Git integration)
npm install -g vercel

# Step 2: Navigate to frontend directory
cd frontend

# Step 3: Deploy via Vercel CLI
vercel --prod
# Or connect GitHub repo in Vercel Dashboard

# Step 4: Set environment variables in Vercel Dashboard
# Go to: Project Settings → Environment Variables
# Add:
#   NEXT_PUBLIC_CONVEX_URL  = https://sleek-herring-766.convex.cloud
```

### 3.3 Vercel Dashboard Configuration

```
1. Go to https://vercel.com → Add New Project
2. Import your GitHub repository (autoinsight-ai)
3. Configure Project:
   - Framework Preset: Next.js
   - Root Directory: frontend/
   - Build Command: next build (default)
   - Output Directory: .next (default)

4. Environment Variables:
   Name: NEXT_PUBLIC_CONVEX_URL
   Value: https://sleek-herring-766.convex.cloud

5. Deploy → Get URL: https://autoinsight-ai.vercel.app
```

### 3.4 Custom Domain Setup

```
1. Go to Vercel Dashboard → Project → Domains
2. Add your domain: autoinsight.com
3. Follow Vercel's DNS instructions:
   - Add CNAME record: cname.vercel-dns.com
   - Or use Vercel's nameservers
4. Wait for DNS propagation (5-30 minutes)
5. SSL certificate auto-provisioned via Let's Encrypt
```

---

## 4. CONVEX BACKEND DEPLOYMENT

### 4.1 Prerequisites

1. **Convex Account** — Sign up at https://convex.dev (Free tier: $0)
2. **Node.js** — v18 or later
3. **Convex CLI** — Installed via npm

### 4.2 Setup Commands

```bash
# Step 1: Install Convex CLI
npx convex

# Step 2: Login to Convex
npx convex login

# Step 3: Deploy to Convex
cd frontend
npx convex deploy

# This deploys all functions in convex/ directory
# Schema is auto-applied on first deploy
```

### 4.3 Convex Dashboard Configuration

```
Dashboard URL: https://dashboard.convex.dev
Project: autoinsight-ai / sleek-herring-766

1. Set Environment Variables:
   Navigate to: Settings → Environment Variables
   
   OPENROUTER_API_KEY = sk-or-v1-...  (REQUIRED)
   ML_SERVICE_URL     = https://ml-service.railway.app  (for V3)
   GOOGLE_CLIENT_ID   = ... (for V5 SSO)
   GITHUB_CLIENT_ID   = ... (for V5 SSO)

2. Configure Auth (for V5 OAuth):
   Navigate to: Settings → Authentication
   - Add Google OAuth provider
   - Add GitHub OAuth provider
   - Configure redirect URIs

3. Monitor Functions:
   Navigate to: Functions → Logs
   - View all function invocations
   - Check for errors
   - Monitor execution time
```

### 4.4 Convex Schema Management

```bash
# Schema is auto-synced when you deploy
# convex/schema.ts defines all tables

# To push schema changes:
cd frontend
npx convex deploy

# To run in development:
npx convex dev
# This watches for file changes and auto-deploys
```

---

## 5. RAILWAY ML SERVICE DEPLOYMENT (V3)

### 5.1 Prerequisites

1. **Railway Account** — Sign up at https://railway.app (Free trial available)
2. **GitHub Repository** for the ml-service files

### 5.2 Deployment Steps

```bash
# Step 1: Create a new GitHub repository for the ML service
# Push these 3 files:
#   - ml-service/main.py
#   - ml-service/requirements.txt
#   - ml-service/Dockerfile

# Step 2: Deploy on Railway
# Go to https://railway.app → New Project → Deploy from GitHub repo
# Select your ml-service repo
# Railway auto-detects Dockerfile and builds

# Step 3: Get deployment URL
# Railway provides: https://ml-service-name.up.railway.app
# Check health: GET https://ml-service-name.up.railway.app/health
```

### 5.3 Railway Configuration

```
Build Settings:
  - Root Directory: / (default)
  - Build Command: docker build -t ml-service .
  - Start Command: docker run -p 8000:8000 ml-service

Resources:
  - Minimum: $5/month (512MB RAM, 1 vCPU)
  - Recommended: $10/month (1GB RAM, 2 vCPU) — for PyCaret/SHAP

Environment Variables: (none required)
```

### 5.4 Testing the Deployment

```bash
# Test health endpoint
curl https://ml-service-name.up.railway.app/health
# Expected: {"status":"healthy","message":"ML Service is running","model_cached":false,"model_type":null}

# Test training
curl -X POST https://ml-service-name.up.railway.app/train \
  -H "Content-Type: application/json" \
  -d '{"data":[{"age":25,"income":50000,"target":1},{"age":30,"income":60000,"target":0}]}'

# Test prediction + explanation
curl -X POST https://ml-service-name.up.railway.app/predict-and-explain \
  -H "Content-Type: application/json" \
  -d '{"data":[{"age":25,"income":50000,"target":1}]}'
```

---

## 6. DOCKER BACKEND DEPLOYMENT

### 6.1 Local Development

```bash
# Start all services
docker compose up -d

# Services started:
#   - FastAPI API        → http://localhost:8000
#   - PostgreSQL 15      → port 5432
#   - Redis 7            → port 6379
#   - MinIO S3           → port 9000 (API), 9001 (Console)
#   - Celery Worker      → background

# View logs
docker compose logs -f api
docker compose logs -f worker

# Stop all services
docker compose down

# Reset all data (deletes volumes)
docker compose down -v
```

### 6.2 Production Deployment (Docker Compose)

```bash
# Step 1: Create .env.production file with all required env vars (see Section 2.3)
# Step 2: Create SSL certificates in ./ssl/ directory

# Step 3: Deploy production
docker compose -f docker-compose.prod.yml up -d

# Step 4: Verify deployment
curl http://localhost/health
# Expected: {"status":"healthy","application":{...}}

# Step 5: Check all services are running
docker compose -f docker-compose.prod.yml ps
```

### 6.3 Production Services

| Service | Replicas | CPU Limit | Memory Limit | Port |
|---------|----------|-----------|--------------|------|
| FastAPI API | 3 | 2 cores | 4 GB | 8000 |
| Nginx Proxy | 2 | 0.5 cores | 256 MB | 80, 443 |
| Celery Worker | 2 | 4 cores | 8 GB | — |
| PostgreSQL 15 | 1 | 2 cores | 2 GB | 5432 |
| Redis 7 | 1 | 1 core | 1 GB | 6379 |
| MinIO S3 | 1 | 1 core | 1 GB | 9000, 9001 |
| Prometheus | 1 | 0.5 cores | 512 MB | 9090 |

---

## 7. KUBERNETES PRODUCTION DEPLOYMENT

### 7.1 Prerequisites

1. **Kubernetes Cluster** — Any K8s cluster (EKS, GKE, AKS, or self-hosted)
2. **kubectl** — Configured with cluster access
3. **Ingress Controller** — nginx-ingress installed
4. **cert-manager** — For SSL certificate management

### 7.2 Deployment Commands

```bash
# Step 1: Create namespace
kubectl apply -f k8s/manifest.yaml

# Step 2: Verify deployments
kubectl get all -n autoinsight

# Step 3: Check pod status
kubectl get pods -n autoinsight -w

# Step 4: View logs
kubectl logs -n autoinsight -l app=autoinsight-api
```

### 7.3 Kubernetes Resources Summary

| Resource | Type | Name | Replicas |
|----------|------|------|----------|
| Namespace | Namespace | autoinsight | — |
| ConfigMap | ConfigMap | autoinsight-config | — |
| Secret | Secret | autoinsight-secrets | — |
| API Deployment | Deployment | autoinsight-api | 3 |
| Worker Deployment | Deployment | autoinsight-worker | 2 |
| Frontend Deployment | Deployment | autoinsight-frontend | 2 |
| API Service | Service | autoinsight-api | ClusterIP |
| Frontend Service | Service | autoinsight-frontend | ClusterIP |
| Ingress | Ingress | autoinsight-ingress | — |
| HPA | HorizontalPodAutoscaler | autoinsight-api-hpa | 3-10 |
| PDB | PodDisruptionBudget | autoinsight-api-pdb | minAvailable: 2 |

### 7.4 Horizontal Pod Autoscaling

```
API Autoscaling:
  - Min Replicas: 3
  - Max Replicas: 10
  - CPU Target: 70%
  - Memory Target: 80%
  
Worker Autoscaling:
  - Min Replicas: 2
  - Max Replicas: 6
  - Scaling based on Celery queue length (via Prometheus metrics)
```

---

## 8. CI/CD PIPELINE WITH GITHUB ACTIONS

### 8.1 Pipeline Stages

```
Push to main/develop or PR to main
         │
         ▼
┌─────────────────┐
│  Quality Check   │
│  ├── Checkout    │
│  ├── Setup Node  │
│  ├── npm ci      │
│  ├── tsc --noEmit│
│  └── npm run lint│
└────────┬────────┘
         │
         │ (if main branch)
         ▼
┌─────────────────┐    ┌─────────────────┐
│  Deploy Convex   │    │  Deploy Vercel   │
│  ├── convex-dev/ │    │  ├── vercel-     │
│  │   action@v1   │    │  │   action@v25 │
│  ├── CONVEX_     │    │  ├── VERCEL_    │
│  │   DEPLOY_KEY  │    │  │   TOKEN      │
│  └── Deploy all  │    │  └── Deploy to  │
│      functions   │    │      production │
└─────────────────┘    └─────────────────┘
```

### 8.2 GitHub Secrets Required

```bash
# Go to: GitHub Repo → Settings → Secrets and variables → Actions

# ── Convex Deploy ──────────────────────────────────────────────────────────
CONVEX_DEPLOY_KEY     # From: Convex Dashboard → Settings → Deploy Key

# ── Vercel Deploy ──────────────────────────────────────────────────────────
VERCEL_TOKEN          # From: Vercel Dashboard → Settings → Tokens
VERCEL_ORG_ID         # From: Vercel Dashboard → Settings → General → ID
VERCEL_PROJECT_ID     # From: Vercel Dashboard → Project → Settings → Project ID
```

### 8.3 Manual Deploy Commands

```bash
# Deploy Convex functions manually
cd frontend
npx convex deploy

# Deploy frontend to Vercel manually
cd frontend
vercel --prod

# Build and push Docker images
docker build -t ghcr.io/autoinsight-ai/backend:latest -f Dockerfile.prod .
docker push ghcr.io/autoinsight-ai/backend:latest
```

---

## 9. MONITORING & LOGGING

### 9.1 Prometheus Monitoring

```bash
# Prometheus is configured via prometheus.yml
# Scrapes metrics from:
#   - FastAPI backend (port 8000 /metrics)
#   - Node exporter (port 9100)
#   - PostgreSQL exporter (port 9187)
#   - Redis exporter (port 9121)

# Access Prometheus dashboard
# http://localhost:9090 (local) or via your domain

# Key metrics to monitor:
#   - API request rate, latency, error rate
#   - Pipeline execution time
#   - Database connection pool size
#   - Redis cache hit ratio
#   - Celery queue length
```

### 9.2 Logging Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOGGING STRATEGY                                 │
│                                                                         │
│  Application Logs:                                                      │
│  ├── FastAPI → stdout (JSON format via structlog)                      │
│  ├── Celery  → stdout (JSON format)                                    │
│  ├── Convex  → Convex Dashboard → Functions → Logs                    │
│  └── Nginx   → /var/log/nginx/access.log + error.log                  │
│                                                                         │
│  Log Levels:                                                            │
│  ├── DEBUG   → Development only (verbose)                               │
│  ├── INFO    → General operational information                         │
│  ├── WARNING → Unexpected but handled situations                       │
│  ├── ERROR   → Errors requiring investigation                         │
│  └── CRITICAL→ System-level failures                                  │
│                                                                         │
│  Log Categories:                                                        │
│  ├── api.*          → API request/response logs                        │
│  ├── pipeline.*     → Pipeline stage execution logs                    │
│  ├── llm.*          → LLM API calls (OpenRouter)                       │
│  ├── database.*     → Database connection pool logs                    │
│  ├── cache.*        → Redis cache operation logs                       │
│  └── auth.*         → Authentication/authorization logs                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Health Check Endpoints

```bash
# Simple health check
GET /health
→ {"status":"healthy","application":{...},"database":{...},"cache":{...}}

# Readiness probe (is app ready to serve traffic?)
GET /health/ready
→ {"status":"ready","timestamp":"2025-06-10T12:00:00Z"}

# Liveness probe (is app alive?)
GET /health/live
→ {"status":"alive","timestamp":"2025-06-10T12:00:00Z"}

# ML Service health
GET https://ml-service.railway.app/health
→ {"status":"healthy","model_cached":true,"model_type":"XGBClassifier"}
```

---

## 10. SSL & SECURITY CONFIGURATION

### 10.1 Nginx SSL Configuration

```nginx
# SSL settings from nginx.conf
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# SSL certificates (mounted from ./ssl/ directory)
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

### 10.2 Security Headers

```nginx
# Applied by Nginx to all responses
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'none';" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
```

### 10.3 Rate Limiting

```bash
# Nginx rate limiting zones
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;    # Auth: 10 req/min
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;    # API: 100 req/min
limit_req_zone $binary_remote_addr zone=upload:10m rate=5r/m;   # Upload: 5 req/min
limit_conn_zone $binary_remote_addr zone=concurrent:10m;         # 10 concurrent connections
```

### 10.4 SQL Injection Protection (Backend)

```python
# backend/middleware/security.py
# Pattern matching for SQL injection attempts
SQL_INJECTION_PATTERNS = [
    r"(\bDROP\b.*\bTABLE\b)",      # DROP TABLE
    r"(\bUNION\b.*\bSELECT\b)",     # UNION SELECT
    r"(';|1=1|1=2|' OR '1'='1)",   # Classic SQL injection
    r"(\bALTER\b.*\bTABLE\b)",      # ALTER TABLE
]
```

---

## 11. DOMAIN & DNS SETUP

### 11.1 DNS Records

```bash
# For autoinsight.com (production)

# Frontend (Vercel)
Type: CNAME
Name: @
Value: cname.vercel-dns.com
TTL: 3600

# API Subdomain (Self-hosted / Docker)
Type: A
Name: api
Value: YOUR_SERVER_IP_ADDRESS
TTL: 3600

# ML Service (Railway)
Type: CNAME
Name: ml
Value: ml-service-name.up.railway.app
TTL: 3600

# Email (Optional)
Type: MX
Name: @
Value: smtp.your-email-provider.com
TTL: 3600
```

### 11.2 SSL Certificate (Let's Encrypt via cert-manager)

```bash
# For Kubernetes deployments with cert-manager
# The Ingress manifest includes:
#   cert-manager.io/cluster-issuer: "letsencrypt-prod"
# This auto-provisions and renews SSL certificates

# For Docker/Nginx deployments:
# 1. Install certbot
apt-get install certbot

# 2. Obtain certificate
certbot certonly --webroot -w /usr/share/nginx/html -d autoinsight.com -d api.autoinsight.com

# 3. Auto-renewal (cron job)
0 0 * * * certbot renew --quiet --post-hook "docker restart autoinsight-nginx"
```

---

## 12. COST ESTIMATION

| Service | Tier | Monthly Cost | Notes |
|---------|------|-------------|-------|
| **Vercel** | Free (Hobby) | $0 | 100GB bandwidth, 6000 build minutes |
| **Convex** | Free (Starter) | $0 | 50GB storage, 5M function calls |
| **Railway (ML)** | Developer | $5-10 | PyCaret needs 1GB+ RAM |
| **PostgreSQL** | Docker (self-hosted) | $0 | Included in server cost |
| **Redis** | Docker (self-hosted) | $0 | Included in server cost |
| **MinIO** | Docker (self-hosted) | $0 | Included in server cost |
| **Cloud VPS** | Hetzner CX22 | $5-10 | 2 vCPU, 4GB RAM, 80GB SSD |
| **Domain** | Namecheap | $10-15/yr | autoinsight.com |
| **SSL** | Let's Encrypt | $0 | Free auto-renewing certificates |
| **OpenRouter** | Pay-as-you-go | $5-20 | Qwen 2.5 72B ~$0.35/M tokens |
| **GitHub Actions** | Free | $0 | 2000 min/month free |
| | **Total (first month)** | **$15-40** | |
| | **Total (ongoing)** | **$10-30/mo** | |

---

*End of Report 2 — Deployment Guide*
