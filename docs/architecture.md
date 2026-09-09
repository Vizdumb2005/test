# Architecture — Enterprise RAG Intelligence

```text
                     ┌──────────────────────────────┐
                     │           Frontend           │
                     │  React + TypeScript + Vite   │
                     │  Tailwind (9 routes, no store│
                     │  lib — direct REST calls)    │
                     └──────────────┬───────────────┘
                                    │  REST / JSON
                                    │  VITE_API_BASE_URL
                                    ▼
                     ┌──────────────────────────────┐
                     │            FastAPI           │
                     │  src/main.py                 │
                     │  RequestID · Telemetry ·     │
                     │  Security headers · Rate     │
                     │  limit · /api/v1 aliases     │
                     └──────────────┬───────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
   ┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
   │  Ingestion     │      │    Retrieval     │      │   Evaluation     │
   │  pipeline.py   │      │  HybridRetriever │      │  BenchmarkRunner │
   │  loaders (pdf/ │      │                  │      │  metrics (P/R/   │
   │  txt/md/docx)  │      │  embed query     │      │  F1/MRR/NDCG/    │
   │  cleaner +     │      │       │          │      │  HitRate)        │
   │  chunker       │      │       ▼          │      │  reports/        │
   └───────┬───────┘      │  ┌──────────┐    │      │  generator       │
           │              │  │ Qdrant   │    │      └────────┬─────────┘
           ▼              │  │ (dense)  │    │               │
   ┌───────────────┐      │  └────┬─────┘    │               ▼
   │  Embeddings    │      │       │          │      ┌──────────────────┐
   │  all-MiniLM-   │◄─────┘  ┌────┴─────┐    │      │  reports/*.json   │
   │  L6-v2 (384d)  │         │  BM25    │◄───┼──────│  reports/*.csv    │
   └───────────────┘         │ (sparse) │    │      │  served via      │
                             └────┬─────┘    │      │  /api/reports/*  │
                                  │          │      └──────────────────┘
                                  ▼          │
                           ┌──────────────┐  │
                           │ Hybrid fusion│  │
                           │ RRF/weighted │  │
                           └──────┬───────┘  │
                                  ▼          │
                           ┌──────────────┐  │
                           │ CrossEncoder │  │
                           │ ms-marco-    │  │
                           │ MiniLM rerank│  │
                           └──────┬───────┘  │
                                  ▼          │
                           ┌──────────────┐  │
                           │   Context    │  │
                           │  construction│  │
                           └──────┬───────┘  │
                                  ▼          │
                           ┌──────────────┐  │
                           │ LLM answer   │  │
                           │ openai/mock  │──┘
                           │ + citations  │
                           └──────────────┘
```

## Request lifecycle (`POST /query`)

1. `RequestContextMiddleware` assigns `X-Request-ID`, records timing into
   process-local session telemetry (`src/core/telemetry.py`).
2. `RateLimitMiddleware` enforces per-minute budgets on expensive prefixes.
3. `HybridRetriever.search()` runs expansion → embedding → dense + BM25 →
   fusion → CrossEncoder rerank, returning per-stage `latency_ms`.
4. The query route builds context, generates an answer (LLM provider or
   extractive fallback), attaches citations with chunk IDs, and returns
   `request_id` for traceability.

## Data stores

| Data | Location | Notes |
|---|---|---|
| Uploaded sources | `data/raw/` | Sanitized filenames, 50 MB default cap |
| Dense vectors | Qdrant collection `enterprise_documents` | Persistent volume `qdrant_data` |
| BM25 index | `data/bm25_index.pkl` | Rebuilt on ingest/delete |
| Benchmark/eval reports | `reports/*.json|csv|md` | Served read-only via `/api/reports/*` |
| Session telemetry | In-process only | Resets on restart, labelled as such in UI |
| Benchmark jobs | In-process job registry | Reports persist to `reports/` |

## Why no persistent monitoring DB

Deliberate scope decision: historical analytics would require Postgres/
Prometheus infrastructure the project does not claim to run. The Monitoring
page is honestly labelled "Current session telemetry".
