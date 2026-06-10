# =============================================================================
# REPORT 3: AUTOINSIGHT AI — COMPLETE DATABASE REPORT
# =============================================================================
# Covers Convex Schema, PostgreSQL Schema, ER Diagrams, Indexes, Data Flow
# =============================================================================

## 📋 TABLE OF CONTENTS
1. [Database Architecture Overview](#1-database-architecture-overview)
2. [Convex Schema (Primary Database)](#2-convex-schema-primary-database)
3. [PostgreSQL Schema (Backend Metadata)](#3-postgresql-schema-backend-metadata)
4. [Entity Relationship Diagram (ERD)](#4-entity-relationship-diagram-erd)
5. [Indexes & Query Performance](#5-indexes--query-performance)
6. [Data Flow Between Databases](#6-data-flow-between-databases)
7. [Redis Cache Schema](#7-redis-cache-schema)
8. [MinIO/S3 Storage Layout](#8-minios3-storage-layout)
9. [Migration Scripts](#9-migration-scripts)
10. [Database Connection Details](#10-database-connection-details)

---

## 1. DATABASE ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATABASE ARCHITECTURE                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   CONVEX (Serverless — Primary)                      │   │
│  │                                                                     │   │
│  │  Tables:                                                             │   │
│  │  ┌────────────┬────────────┬───────────┬────────────┬────────────┐   │   │
│  │  │  users     │  uploads   │ datasets  │ pipeline-  │  reports   │   │   │
│  │  │            │            │           │  Results   │            │   │   │
│  │  ├────────────┼────────────┼───────────┼────────────┼────────────┤   │   │
│  │  │dashboard   │conversat-  │auditLog   │prompts     │scheduled-  │   │   │
│  │  │  s         │  ions      │           │            │  Reports   │   │   │
│  │  ├────────────┼────────────┼───────────┼────────────┼────────────┤   │   │
│  │  │dataset-    │joined-     │           │            │            │   │   │
│  │  │ Relations  │Datasets    │           │            │            │   │   │
│  │  └────────────┴────────────┴───────────┴────────────┴────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               POSTGRESQL 15 (Backend Metadata)                       │   │
│  │                                                                     │   │
│  │  Tables:                                                             │   │
│  │  ┌──────────┬───────────┬─────────────┬──────────┬──────────────┐  │   │
│  │  │  users   │ pipelines │data_models  │ reports  │conversations │  │   │
│  │  ├──────────┼───────────┼─────────────┼──────────┼──────────────┤  │   │
│  │  │ prompts  │audit_log  │   files     │_migrat-  │              │  │   │
│  │  │          │           │             │  ions    │              │  │   │
│  │  └──────────┴───────────┴─────────────┴──────────┴──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐     │
│  │  REDIS 7     │    │  MINIO S3    │    │  ML SERVICE (Joblib)     │     │
│  │  (Cache)     │    │ (File Store) │    │  (Model Cache)           │     │
│  │              │    │              │    │                          │     │
│  │  pipeline:{} │    │ uploads/     │    │  models/best_model.pkl   │     │
│  │  df_cache:{} │    │ reports/     │    │  models/model_meta.pkl   │     │
│  │  schema:{}   │    │ data_models/ │    │                          │     │
│  └──────────────┘    └──────────────┘    └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CONVEX SCHEMA (PRIMARY DATABASE)

### 2.1 Table: users

**File:** `frontend/convex/schema.ts`

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"users">` | Auto | Primary | Auto-generated document ID |
| `_creationTime` | `number` | Auto | — | Auto-generated creation timestamp |
| `email` | `string` | ✅ | **by_email** | User email address (unique) |
| `name` | `string` | ✅ | — | User display name |
| `passwordHash` | `string` | ✅ | — | BCrypt password hash |
| `role` | `"admin" \| "analyst" \| "viewer"` | ✅ | — | RBAC role |
| `createdAt` | `number` | ✅ | — | Unix timestamp of creation |
| `lastLogin` | `number?` | ❌ | — | Unix timestamp of last login |

**Indexes:**
```typescript
.index("by_email", ["email"])  // Used for login lookup
```

### 2.2 Table: uploads

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"uploads">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner user ID |
| `fileName` | `string` | ✅ | — | Original CSV filename |
| `fileSize` | `number` | ✅ | — | File size in bytes |
| `fileStorageId` | `string?` | ❌ | — | Convex storage ID |
| `status` | `"pending"\|"uploading"\|"processing"\|"completed"\|"failed"` | ✅ | — | Upload processing status |
| `rowCount` | `number?` | ❌ | — | Number of rows detected |
| `columnCount` | `number?` | ❌ | — | Number of columns detected |
| `createdAt` | `number` | ✅ | — | Creation timestamp |
| `completedAt` | `number?` | ❌ | — | Completion timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])  // List uploads by user
```

### 2.3 Table: pipelineResults

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"pipelineResults">` | Auto | Primary | Auto-generated |
| `uploadId` | `Id<"uploads">` | ✅ | **by_upload** | Source upload |
| `userId` | `Id<"users">` | ✅ | — | Owner |
| `status` | `"queued"\|"running"\|"completed"\|"failed"` | ✅ | — | Pipeline status |
| `schemaInference` | `any?` | ❌ | — | Stage 1 result (JSON) |
| `cleaningPlan` | `any?` | ❌ | — | Stage 2 result (JSON) |
| `unifiedDataModel` | `any?` | ❌ | — | Stage 3/4 result (JSON) |
| `processingTimeMs` | `number?` | ❌ | — | Total processing time |
| `error` | `string?` | ❌ | — | Error message if failed |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_upload", ["uploadId"])  // Get pipeline by upload
```

### 2.4 Table: reports

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"reports">` | Auto | Primary | Auto-generated |
| `uploadId` | `Id<"uploads">` | ✅ | — | Source upload |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner |
| `title` | `string` | ✅ | — | Report title |
| `sections` | `Array<{sectionType, title, content, confidence}>` | ✅ | — | 8 report sections |
| `overallConfidence` | `number` | ✅ | — | Average confidence 0-1 |
| `exportFormats` | `string[]?` | ❌ | — | Available export formats |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])  // List reports by user
```

### 2.5 Table: dashboards

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"dashboards">` | Auto | Primary | Auto-generated |
| `uploadId` | `Id<"uploads">` | ✅ | — | Source upload |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner |
| `title` | `string` | ✅ | — | Dashboard title |
| `layout` | `Array<{i, x, y, w, h}>` | ✅ | — | Grid layout config |
| `widgets` | `any` | ✅ | — | Chart widget configs |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])  // List dashboards by user
```

### 2.6 Table: conversations

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"conversations">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | — | Owner |
| `uploadId` | `Id<"uploads">` | ✅ | — | Related dataset |
| `messages` | `Array<{role, content, sqlGenerated?, chartConfig?, timestamp}>` | ✅ | — | Chat history (max 20) |
| `createdAt` | `number` | ✅ | — | Creation timestamp |
| `updatedAt` | `number` | ✅ | — | Last update timestamp |

**Indexes:**
```typescript
.index("by_user_upload", ["userId", "uploadId"])  // Find conversation by user + dataset
```

### 2.7 Table: datasets

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"datasets">` | Auto | Primary | Auto-generated |
| `uploadId` | `Id<"uploads">` | ✅ | **by_upload** | Source upload |
| `userId` | `Id<"users">` | ✅ | — | Owner |
| `columns` | `string[]` | ✅ | — | Column names |
| `rowCount` | `number` | ✅ | — | Number of rows |
| `data` | `any` | ✅ | — | Raw data (array of objects) |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_upload", ["uploadId"])  // Get dataset by upload
```

### 2.8 Table: auditLog

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"auditLog">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | **by_user** | Actor |
| `action` | `string` | ✅ | — | Action performed |
| `resourceType` | `string` | ✅ | **by_resource** | Resource type |
| `resourceId` | `string?` | ❌ | — | Resource identifier |
| `details` | `any?` | ❌ | — | JSON details |
| `ip` | `string?` | ❌ | — | Client IP |
| `timestamp` | `number` | ✅ | **by_timestamp** | Event timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])
.index("by_resource", ["resourceType", "resourceId"])
.index("by_timestamp", ["timestamp"])
```

### 2.9 Table: prompts

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"prompts">` | Auto | Primary | Auto-generated |
| `name` | `string` | ✅ | **by_name** | Prompt template name |
| `version` | `number` | ✅ | — | Template version |
| `template` | `string` | ✅ | — | Template content |
| `provider` | `string` | ✅ | — | LLM provider |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_name", ["name"])  // Lookup prompts by name
```

### 2.10 Table: datasetRelations (V4)

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"datasetRelations">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner |
| `name` | `string` | ✅ | — | Relation name |
| `description` | `string?` | ❌ | — | Description |
| `sourceUploadId` | `Id<"uploads">` | ✅ | — | Source dataset |
| `targetUploadId` | `Id<"uploads">` | ✅ | — | Target dataset |
| `sourceColumn` | `string` | ✅ | — | Source join column |
| `targetColumn` | `string` | ✅ | — | Target join column |
| `joinType` | `"inner"\|"left"\|"right"\|"outer"` | ✅ | — | Join type |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])  // List relations by user
```

### 2.11 Table: joinedDatasets (V4)

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"joinedDatasets">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner |
| `relationId` | `Id<"datasetRelations">` | ✅ | **by_relation** | Relation |
| `columns` | `string[]` | ✅ | — | Joined column names |
| `rowCount` | `number` | ✅ | — | Number of result rows |
| `data` | `any` | ✅ | — | Joined data (JSON) |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])
.index("by_relation", ["relationId"])  // Get joined result by relation
```

### 2.12 Table: scheduledReports (V5)

| Field | Type | Required | Index | Description |
|-------|------|----------|-------|-------------|
| `_id` | `Id<"scheduledReports">` | Auto | Primary | Auto-generated |
| `userId` | `Id<"users">` | ✅ | **by_user** | Owner |
| `reportId` | `Id<"reports">` | ✅ | — | Report to send |
| `email` | `string` | ✅ | — | Recipient email |
| `frequency` | `"daily"\|"weekly"\|"monthly"` | ✅ | — | Send frequency |
| `nextSend` | `number` | ✅ | — | Next scheduled send |
| `lastSent` | `number?` | ❌ | — | Last send timestamp |
| `createdAt` | `number` | ✅ | — | Creation timestamp |

**Indexes:**
```typescript
.index("by_user", ["userId"])  // List schedules by user
```

---

## 3. POSTGRESQL SCHEMA (BACKEND METADATA)

### 3.1 Table: users

**File:** `scripts/migrate.py` (MIGRATION_V001)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `email` | `VARCHAR(255)` | UNIQUE NOT NULL | User email |
| `password_hash` | `VARCHAR(255)` | NOT NULL | BCrypt hash |
| `name` | `VARCHAR(255)` | NOT NULL | Display name |
| `role` | `VARCHAR(50)` | NOT NULL DEFAULT 'analyst', CHECK (role IN ('admin','analyst','viewer')) | RBAC role |
| `is_active` | `BOOLEAN` | DEFAULT TRUE | Account active |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Update timestamp |
| `last_login_at` | `TIMESTAMPTZ` | — | Last login timestamp |

### 3.2 Table: pipelines

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | `UUID` | FK → users(id) ON DELETE CASCADE | Owner |
| `status` | `VARCHAR(50)` | NOT NULL DEFAULT 'queued', CHECK(IN 'queued','running','completed','failed','cancelled') | Pipeline status |
| `file_name` | `VARCHAR(255)` | — | Source filename |
| `file_size` | `BIGINT` | — | File size in bytes |
| `file_hash` | `VARCHAR(64)` | — | MD5 hash |
| `llm_provider` | `VARCHAR(50)` | DEFAULT 'groq' | LLM provider used |
| `stages_completed` | `TEXT[]` | DEFAULT '{}' | Array of completed stages |
| `error_message` | `TEXT` | — | Error details |
| `started_at` | `TIMESTAMPTZ` | — | Start timestamp |
| `completed_at` | `TIMESTAMPTZ` | — | Completion timestamp |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |

### 3.3 Table: data_models

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `pipeline_id` | `UUID` | FK → pipelines(id) ON DELETE CASCADE | Source pipeline |
| `user_id` | `UUID` | FK → users(id) ON DELETE CASCADE | Owner |
| `model_json` | `JSONB` | NOT NULL | Full UnifiedDataModel |
| `confidence_avg` | `FLOAT` | — | Average confidence |
| `column_count` | `INTEGER` | — | Number of columns |
| `row_count` | `BIGINT` | — | Number of rows |
| `version` | `INTEGER` | DEFAULT 1 | Model version |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |

### 3.4 Table: reports

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `data_model_id` | `UUID` | FK → data_models(id) ON DELETE CASCADE | Source data model |
| `user_id` | `UUID` | FK → users(id) ON DELETE CASCADE | Owner |
| `title` | `VARCHAR(255)` | — | Report title |
| `report_bundle` | `JSONB` | — | Full report content |
| `export_urls` | `JSONB` | — | Export file URLs |
| `status` | `VARCHAR(50)` | DEFAULT 'pending', CHECK(IN 'pending','generating','completed','failed') | Generation status |
| `overall_confidence` | `FLOAT` | — | Average confidence |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |

### 3.5 Table: conversations

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | `UUID` | FK → users(id) ON DELETE CASCADE | Owner |
| `dataset_id` | `UUID` | — | Related dataset |
| `context` | `JSONB` | — | Conversation context |
| `turn_count` | `INTEGER` | DEFAULT 0 | Number of turns |
| `is_active` | `BOOLEAN` | DEFAULT TRUE | Active status |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Update timestamp |

### 3.6 Table: prompts

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Auto-incrementing ID |
| `name` | `VARCHAR(255)` | NOT NULL | Template name |
| `version` | `INTEGER` | NOT NULL | Template version |
| `template` | `TEXT` | NOT NULL | Prompt template |
| `description` | `TEXT` | — | Description |
| `stage` | `INTEGER` | — | Pipeline stage |
| `is_active` | `BOOLEAN` | DEFAULT TRUE | Active flag |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |
| | | UNIQUE(name, version) | Unique constraint |

### 3.7 Table: audit_log

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | Auto-incrementing ID |
| `user_id` | `UUID` | FK → users(id) ON DELETE SET NULL | Actor |
| `action` | `VARCHAR(255)` | NOT NULL | Action performed |
| `resource_type` | `VARCHAR(50)` | — | Resource category |
| `resource_id` | `UUID` | — | Resource identifier |
| `details` | `JSONB` | — | Action details |
| `ip_address` | `VARCHAR(45)` | — | Client IP |
| `user_agent` | `TEXT` | — | User agent string |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Event timestamp |

### 3.8 Table: files

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK DEFAULT gen_random_uuid() | Unique identifier |
| `user_id` | `UUID` | FK → users(id) ON DELETE CASCADE | Owner |
| `file_name` | `VARCHAR(255)` | NOT NULL | Original filename |
| `file_size` | `BIGINT` | — | File size |
| `file_hash` | `VARCHAR(64)` | — | MD5 hash |
| `mime_type` | `VARCHAR(255)` | — | MIME type |
| `s3_key` | `VARCHAR(512)` | — | S3 object key |
| `s3_bucket` | `VARCHAR(255)` | — | S3 bucket name |
| `metadata` | `JSONB` | — | File metadata |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation timestamp |

### 3.9 Table: _migrations (Migration Tracking)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Auto-incrementing ID |
| `version` | `INTEGER` | NOT NULL | Migration version number |
| `name` | `VARCHAR(255)` | NOT NULL | Migration name |
| `applied_at` | `TIMESTAMPTZ` | DEFAULT NOW() | When applied |
| `checksum` | `VARCHAR(64)` | — | Migration checksum |

---

## 4. ENTITY RELATIONSHIP DIAGRAM (ERD)

### 4.1 Convex ERD

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CONVEX ENTITY RELATIONSHIPS                            │
│                                                                                 │
│                                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌───────────────┐     ┌──────────┐         │
│  │  users   │────▶│ uploads  │────▶│pipelineResults│────▶│ reports  │         │
│  │          │1   N│          │1   N│               │1   N│          │         │
│  │ PK: _id  │     │ FK: userId│    │FK: uploadId   │    │FK: uploadId│        │
│  │ email    │     │ status   │    │ status         │    │ userId    │         │
│  │ role     │     │ fileName │    │ unifiedDataModel│   │ sections  │         │
│  └──────────┘     └──────────┘    └────────────────┘     └──────────┘         │
│       │                                                                         │
│       │                                                                         │
│       ▼                                                                         │
│  ┌──────────┐     ┌──────────┐     ┌───────────────┐     ┌───────────────┐    │
│  │ datasets │────▶│conversat-│     │ auditLog      │     │ dashboards   │     │
│  │          │1   N│  ions    │     │                │      │              │     │
│  │ FK:uploadId│   │         │     │ FK: userId     │     │ FK: userId   │     │
│  │ data (JSON)│   │ FK:userId │    │ action         │     │ widgets      │     │
│  │ columns   │   │ messages  │    │ resourceType   │     │ layout       │     │
│  └──────────┘     └──────────┘    └────────────────┘     └──────────────┘     │
│                                                                                 │
│       │                           (V4)                                          │
│       ▼                                                                         │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐       │
│  │ datasetRelations │────▶│ joinedDatasets   │     │ scheduledReports │ (V5)  │
│  │ (V4)             │1   N│ (V4)             │     │                  │       │
│  │ FK: userId       │     │ FK: relationId   │     │ FK: userId       │       │
│  │ sourceUploadId   │     │ data (joined)    │     │ email, frequency │       │
│  │ targetUploadId   │     │ columns          │     │ nextSend         │       │
│  │ joinType         │     │ rowCount         │     │ reportId         │       │
│  └──────────────────┘     └──────────────────┘     └──────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 PostgreSQL ERD

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         POSTGRESQL ENTITY RELATIONSHIPS                           │
│                                                                                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────┐           │
│  │  users   │────▶│pipelines │────▶│ data_models  │────▶│ reports  │           │
│  │          │1   N│          │1   N│              │1   N│          │           │
│  │ PK: id   │     │ FK:user_id│    │FK:pipeline_id│    │FK:data_model_id│       │
│  │ email    │     │ status   │    │ model_json→UDM│    │ FK:user_id│           │
│  │ role     │     │ file_name│    │ confidence_avg│    │ report_bundle│         │
│  └──────────┘     └──────────┘    └──────────────┘    │ export_urls │         │
│       │                                                └──────────────┘         │
│       │                                                                          │
│       ▼                                                                          │
│  ┌──────────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────┐       │
│  │ files        │     │conversat-│     │ audit_log    │     │ prompts  │       │
│  │              │     │  ions    │     │              │     │          │       │
│  │ FK: user_id  │     │ FK:user_id│    │ FK: user_id  │     │ name,    │       │
│  │ s3_key, bucket│    │ dataset_id│   │ action       │     │ version  │       │
│  │ file_hash    │     │ context  │     │ resource_type│     │ template │       │
│  └──────────────┘     └──────────┘    └──────────────┘    └──────────┘       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Data Flow Between Tables

```
CSV Upload Flow:
  uploads (status=pending) → uploads (status=uploading) → uploads (status=processing)
    → datasets (data stored) → pipelineResults (status=running)
    → pipelineResults (stage1→stage2→stage3→stage4, status=completed)
    → uploads (status=completed) → reports (sections generated) 

NLQ Chat Flow:
  conversations (created) → datasets (data queried) → conversations (message added)

V4 Joins Flow:
  datasetRelations (created) → datasets(src) + datasets(tgt) → joinedDatasets (cached)

V5 Scheduling Flow:
  reports (generated) → scheduledReports (created with frequency)
```

---

## 5. INDEXES & QUERY PERFORMANCE

### 5.1 Convex Indexes Summary

| Table | Index Name | Fields | Purpose |
|-------|-----------|--------|---------|
| `users` | `by_email` | `email` | Fast login by email |
| `uploads` | `by_user` | `userId` | List all uploads for a user |
| `pipelineResults` | `by_upload` | `uploadId` | Get pipeline for an upload |
| `reports` | `by_user` | `userId` | List reports by user |
| `dashboards` | `by_user` | `userId` | List dashboards by user |
| `conversations` | `by_user_upload` | `userId, uploadId` | Get conversation by user+dataset |
| `datasets` | `by_upload` | `uploadId` | Get dataset for an upload |
| `auditLog` | `by_user` | `userId` | Get audit logs by user |
| `auditLog` | `by_resource` | `resourceType, resourceId` | Query by resource |
| `auditLog` | `by_timestamp` | `timestamp` | Time-based queries |
| `prompts` | `by_name` | `name` | Lookup prompt by name |
| `datasetRelations` | `by_user` | `userId` | List relations by user |
| `joinedDatasets` | `by_user` | `userId` | List joined datasets |
| `joinedDatasets` | `by_relation` | `relationId` | Get joined result |
| `scheduledReports` | `by_user` | `userId` | List schedules by user |

### 5.2 PostgreSQL Indexes Summary

```sql
-- Created by scripts/migrate.py (v002: indexes)

-- Pipeline indexes
CREATE INDEX idx_pipelines_user_id ON pipelines(user_id);
CREATE INDEX idx_pipelines_status ON pipelines(status);
CREATE INDEX idx_pipelines_created_at ON pipelines(created_at DESC);

-- Data model indexes
CREATE INDEX idx_data_models_pipeline_id ON data_models(pipeline_id);
CREATE INDEX idx_data_models_user_id ON data_models(user_id);

-- Report indexes
CREATE INDEX idx_reports_data_model_id ON reports(data_model_id);
CREATE INDEX idx_reports_user_id ON reports(user_id);
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);

-- Conversation indexes
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- Audit log indexes
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action);

-- Prompt indexes
CREATE INDEX idx_prompts_name_version ON prompts(name, version DESC);

-- File indexes
CREATE INDEX idx_files_user_id ON files(user_id);
CREATE INDEX idx_files_file_hash ON files(file_hash);
```

### 5.3 Common Query Patterns

```typescript
// === CONVEX QUERY PATTERNS ===

// 1. Get user by email (login)
ctx.db.query("users").withIndex("by_email", (q) => q.eq("email", email)).unique();

// 2. List uploads for a user (dashboard)
ctx.db.query("uploads").withIndex("by_user", (q) => q.eq("userId", userId)).order("desc").collect();

// 3. Get dataset by upload (chart builder)
ctx.db.query("datasets").withIndex("by_upload", (q) => q.eq("uploadId", uploadId)).first();

// 4. List reports for a user (report list)
ctx.db.query("reports").withIndex("by_user", (q) => q.eq("userId", userId)).order("desc").collect();

// 5. Get conversation by user + upload (NLQ chat)
ctx.db.query("conversations").withIndex("by_user_upload", (q) => q.eq("userId", userId).eq("uploadId", uploadId)).first();

// 6. Get joined dataset by relation (V4)
ctx.db.query("joinedDatasets").withIndex("by_relation", (q) => q.eq("relationId", relationId)).first();

// 7. List audit logs with filters
let q = ctx.db.query("auditLog");
if (userId) q = q.withIndex("by_user", (qIdx) => qIdx.eq("userId", userId));
if (resourceType) q = q.withIndex("by_resource", (qIdx) => qIdx.eq("resourceType", resourceType));
return await q.order("desc").take(limit || 50);


// === POSTGRESQL QUERY PATTERNS ===

// 1. Insert pipeline with UUID
await insert_one("pipelines", {
  pipeline_id: pipelineId,
  status: "completed",
  stages_completed: stagesCompleted,
  ...
});

// 2. Fetch by condition
await fetch_one("pipelines", { pipeline_id: pipelineId });

// 3. Fetch multiple with pagination
await fetch_many("pipelines", { user_id: userId }, "created_at DESC", 20, 0);

// 4. Update specific fields
await update_one("pipelines", { status: "failed" }, { pipeline_id: pipelineId });
```

---

## 6. DATA FLOW BETWEEN DATABASES

### 6.1 When Does Data Go Where?

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW DECISION MAP                                │
│                                                                              │
│  User Action                      → Database Used                             │
│  ────────────────────────────────────────────────────────────────────────    │
│  User Registration / Login        → Convex (users table)                     │
│  User Uploads CSV                 → Convex (uploads + datasets tables)       │
│  Upload file bytes stored         → Convex Storage (fileStorageId)            │
│  Pipeline Execution               → Convex (pipelineResults table)            │
│  Report Generation                → Convex (reports table)                    │
│  Dashboard Save                   → Convex (dashboards table)                 │
│  NLQ Chat                         → Convex (conversations table)              │
│  Audit Log                        → Convex (auditLog table)                   │
│  Dataset Join (V4)                → Convex (datasetRelations + joinedDatasets)│
│  Email Schedule (V5)              → Convex (scheduledReports table)           │
│  Chart Builder Layout             → Convex (dashboards table)                 │
│                                                                              │
│  ─── Backend Python Pipeline ───                                              │
│  Pipeline Execution Tracking      → PostgreSQL (pipelines table)              │
│  UDM Storage (JSONB)              → PostgreSQL (data_models table)            │
│  Report Bundle Storage            → PostgreSQL (reports table)                │
│  Prompt Templates                 → PostgreSQL (prompts table)                │
│  Backend Audit Log                → PostgreSQL (audit_log table)              │
│  File Records                     → PostgreSQL (files table)                  │
│  Raw CSV files                    → MinIO S3 (autoinsight-files bucket)       │
│  Parquet snapshots                → MinIO S3 (autoinsight-files bucket)       │
│  Pipeline State (cache)           → Redis (pipeline:{pipelineId})             │
│  DataFrame Cache                  → Redis (df_cache:{pipelineId})             │
│  SSE Event State                  → Redis (sse:{pipelineId})                  │
│                                                                              │
│  ─── ML Service (V3) ───                                                     │
│  Trained Model                    → Local disk (models/best_model.pkl)        │
│  Model Metadata                   → Local disk (models/model_meta.pkl)        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. REDIS CACHE SCHEMA

### 7.1 Redis Key Patterns

```bash
# Pipeline State
pipeline:{pipelineId}          → JSON { status, global_progress, stages, ... }
sse:{pipelineId}               → SSE event state

# DataFrame Cache (Stage 2 I/O)
df_cache:stage2_input:{pipelineId}   → Serialized Polars DataFrame
df_cache:stage2_output:{pipelineId}  → Serialized Polars DataFrame

# Schema Cache (Stage 1)
schema:{fileHash}              → SchemaInferenceResponse JSON

# Cleaning State
cleaning_approved:{pipelineId} → Approved cleaning operations array
cleaning_plan:{pipelineId}     → CleaningPlan JSON

# Upload Progress
upload_progress:{uploadId}     → Upload progress state JSON

# Cache Warming
cache_warm:{datasetId}         → { warmed_at: timestamp }

# Session Data (Optional)
session:{sessionId}            → User session data
```

---

## 8. MINIO/S3 STORAGE LAYOUT

```
autoinsight-files/
├── uploads/
│   ├── {upload_id}/
│   │   ├── original.csv          ← Raw uploaded CSV
│   │   ├── staging/              ← Chunk upload staging
│   │   │   ├── chunk_0
│   │   │   ├── chunk_1
│   │   │   └── ...
│   │   └── metadata.json
│   └── ...
│
├── pipeline/
│   └── {pipeline_id}/
│       ├── stage1_output.json
│       ├── stage2_output.parquet
│       └── stage4_output.parquet
│
├── data_models/
│   └── {pipeline_id}/
│       └── unified_data_model.json   ← Complete UDM for report gen
│
├── reports/
│   └── {report_id}/
│       ├── report.html
│       ├── report.md
│       ├── report.pdf
│       └── report.xlsx
│
└── exports/
    └── {user_id}/
        └── {export_id}.{format}
```

---

## 9. MIGRATION SCRIPTS

### 9.1 Migration History

```
Migration: v001_core_schema
Applied:   [timestamp]
Contents:  Creates ALL 8 PostgreSQL tables with constraints
  - users, pipelines, data_models, reports
  - conversations, prompts, audit_log, files

Migration: v002_indexes
Applied:   [timestamp]
Contents:  Creates 14 performance indexes
  - Indexes on foreign keys, status, timestamps
  - Composite index on prompts(name, version DESC)
  - Index on audit_log(action) for filtering
```

### 9.2 Running Migrations

```bash
# Check pending migrations (dry-run)
python scripts/migrate.py --check

# Apply pending migrations
python scripts/migrate.py

# Apply migrations AND seed default data
python scripts/migrate.py --seed

# Output expected:
# Migration Summary: 2 migrations applied
#   v001: core_schema (2025-06-10 12:00:00)
#   v002: indexes (2025-06-10 12:00:05)
```

### 9.3 Migration Validation

```python
# Migration checksum verification would go here in production
# Currently tracked by:
#   - version number (sequential integers)
#   - applied_at timestamp
#   - name field
# Future: Add SHA256 checksum of SQL content
```

---

## 10. DATABASE CONNECTION DETAILS

### 10.1 Convex Connection

```typescript
// Frontend (src/app/providers.tsx)
const convex = new ConvexReactClient(
  process.env.NEXT_PUBLIC_CONVEX_URL || "https://sleek-herring-766.convex.cloud"
);

// Deployment URL: https://sleek-herring-766.convex.cloud
// Dashboard: https://dashboard.convex.dev
// Project: autoinsight-ai / sleek-herring-766
// Functions: convex/ directory
```

### 10.2 PostgreSQL Connection

```python
# Backend (backend/database.py)
# Connection pool configuration:
#   - dsn: settings.DATABASE_URL (from .env)
#   - min_size: 2 (always available)
#   - max_size: 20 (concurrent operations)
#   - max_queries: 50000 (queries per connection before recycling)
#   - max_inactive_connection_lifetime: 300s (5 min idle timeout)
#   - command_timeout: 60s

# Default connection string:
# postgresql://autoinsight:changeme@localhost:5432/autoinsight
```

### 10.3 Redis Connection

```python
# Backend (backend/cache.py)
# Connection:
#   - url: settings.REDIS_URL (from .env)
#   - decode_responses: True

# Default connection string:
# redis://localhost:6379/0

# Celery broker: redis://localhost:6379/1
# Celery backend: redis://localhost:6379/2
```

### 10.4 MinIO/S3 Connection

```python
# Backend (backend/storage.py)
# Connection:
#   - endpoint: settings.S3_ENDPOINT (default: http://localhost:9000)
#   - access_key: settings.S3_ACCESS_KEY (default: minioadmin)
#   - secret_key: settings.S3_SECRET_KEY (default: minioadmin)
#   - bucket: settings.S3_BUCKET (default: autoinsight-files)
#   - region: settings.S3_REGION (default: us-east-1)
```

### 10.5 ML Service (No Persistent DB)

```python
# ML Service stores trained models on disk:
# ml-service/models/best_model.pkl    ← PyCaret trained model
# ml-service/models/model_meta.pkl    ← Model metadata (joblib)
# 
# No database needed — model is loaded from disk on each request
# Cache is ephemeral (lost on restart, retrained on demand)
```

---

## QUICK REFERENCE: TABLE COUNTS

| Database | Table/Collection | Records | Purpose |
|----------|-----------------|---------|---------|
| **Convex** | users | Varies | User accounts |
| Convex | uploads | Varies | File uploads |
| Convex | pipelineResults | Varies | Pipeline execution |
| Convex | reports | Varies | Generated reports |
| Convex | dashboards | Varies | Dashboard layouts |
| Convex | conversations | Varies | NLQ chat history |
| Convex | datasets | Varies | Raw data storage |
| Convex | auditLog | Varies | Audit trail |
| Convex | prompts | Varies | Prompt templates |
| Convex | datasetRelations | Varies (V4) | Join definitions |
| Convex | joinedDatasets | Varies (V4) | Cached join results |
| Convex | scheduledReports | Varies (V5) | Email schedules |
| | | | |
| **PostgreSQL** | users | Varies | User accounts |
| PostgreSQL | pipelines | Varies | Pipeline tracking |
| PostgreSQL | data_models | Varies | UDM JSONB |
| PostgreSQL | reports | Varies | Report bundles |
| PostgreSQL | conversations | Varies | NLQ history |
| PostgreSQL | prompts | Varies | Templates |
| PostgreSQL | audit_log | Varies | Audit trail |
| PostgreSQL | files | Varies | File index |
| PostgreSQL | _migrations | 2 | Migration tracking |
| | | | |
| **Redis** | pipeline:* | Varies | Cache keys |
| **MinIO** | autoinsight-files | Varies | S3 objects |
| **ML Service** | models/* | Ephemeral | Trained models |

---

*End of Report 3 — Database Schema*
