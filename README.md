# AutoInsight AI — Agentic Data Analysis & Report Generation System

An autonomous AI agent that ingests raw CSV data, automatically understands its structure, cleans it, discovers hidden relationships, engineers meaningful features, and generates professional analytical reports — all with **zero LLM API cost**.

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> autoinsight-ai
cd autoinsight-ai
pip install -r requirements.txt

# 2. Configure LLM (OpenRouter Only)
cp frontend/.env.example frontend/.env.local
# Edit .env.local: Set OPENROUTER_API_KEY from https://openrouter.ai/keys

# 3. Start infrastructure
docker-compose up -d postgres redis minio

# 4. Run migrations
python scripts/migrate.py

# 5. Start development server
uvicorn backend.api:app --reload --port 8000

# 6. Run tests
pytest --cov=backend --cov-report=term-missing
```

## Architecture

```
5-Layer System Architecture:
  Layer 1: React/Next.js PWA (Frontend)
  Layer 2: FastAPI + JWT + RBAC (API Gateway)
  Layer 3: LangGraph Agents (AI Orchestration)
  Layer 4: Polars + DuckDB + DataPrep (Data Engine)
  Layer 5: PostgreSQL + Redis + MinIO (Storage)
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Zero-Cost LLM** | OpenRouter: qwen/qwen3-coder:free + meta-llama/llama-4-maverick:free = $0 |
| **Deterministic-First** | LLM only for reasoning; 60%+ of compute is deterministic |
| **4-Stage Pipeline** | CSV → JSON → Clean → Relationships → Columns → UDM |
| **4-Phase Reports** | Profile → 8 Parallel Agents → Validate → Export |
| **Confidence Gating** | ≥0.65 gate, retry (3x), fallback to rule engine |
| **Full Audit Trail** | Every transformation logged with lineage |
| **PWA Interface** | Offline-capable, responsive, interactive dashboards |

## Project Structure

```
autoinsight-ai/
├── backend/
│   ├── api.py              # FastAPI application
│   ├── auth.py             # JWT + RBAC
│   ├── config.py           # Pydantic Settings
│   ├── database.py         # asyncpg connection pool
│   ├── llm_factory.py      # Qwen 2.5 + Llama provider
│   ├── prompt_registry.py  # Versioned prompt management
│   ├── schemas.py          # All Pydantic v2 models
│   ├── tasks.py            # Celery async tasks
│   ├── tools.py            # Polars/SciPy deterministic tools
│   ├── middleware/         # Auth + logging middleware
│   ├── pipeline/           # 4-stage data pipeline
│   │   ├── stage1_csv_to_json.py
│   │   ├── stage2_data_clean.py
│   │   ├── stage3_langgraph_agent.py
│   │   └── stage4_column_engine.py
│   ├── report/             # 4-phase report engine
│   │   ├── phase1_profiling.py
│   │   ├── phase2_sub_agents.py
│   │   ├── phase3_validation.py
│   │   └── phase4_export.py
│   └── nlq/                # NLQ chat + dashboard
│       ├── chat.py
│       └── dashboard.py
├── scripts/
│   └── migrate.py          # PostgreSQL migrations
├── tests/
│   ├── test_schemas.py     # Pydantic model validation
│   ├── test_tools.py       # Deterministic tool tests
│   └── test_auth.py        # JWT + RBAC tests
├── docker-compose.yml      # PostgreSQL + Redis + MinIO
├── Dockerfile              # Multi-stage build
├── requirements.txt        # Python dependencies
└── .env.example            # Environment configuration
```

## Phase 1: Foundation (✅ Complete)

Phase 1 establishes the project foundation:
- Project structure, configuration, Docker infrastructure
- All Pydantic v2 data models (24+ models)
- Deterministic data processing tools (15+ functions)
- FastAPI application with health checks
- LLM factory (Groq + Ollama) with structured output
- Versioned prompt registry (12 prompt templates)
- JWT authentication + RBAC middleware
- Pipeline stubs (stages 1-4)
- Report engine stubs (phases 1-4)
- Celery async task configuration
- Database migration scripts (7 tables)
- Unit test suite (50+ tests, 80%+ coverage)
- Comprehensive Phase 1 Completion Report

## Phases 2-5 (Upcoming)

| Phase | Weeks | Focus | Story Points |
|-------|-------|-------|-------------|
| **Phase 2** | 3-4 | Core Pipeline (Stages 1-4 implementation) | 60 |
| **Phase 3** | 5-6 | Report Engine (Phases 1-4 implementation) | 34 |
| **Phase 4** | 7-8 | Frontend (React/Next.js PWA) | 58 |
| **Phase 5** | 9-10 | Integration, Testing & Deploy | 55 |

## License

MIT License — See LICENSE file for details.
