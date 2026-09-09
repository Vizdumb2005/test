# Enterprise RAG Intelligence

An **evaluation-driven, retrieval-transparent** hybrid RAG platform. Every answer traces
`query → expansion → dense + BM25 → fusion → CrossEncoder rerank → evidence → generation`,
with measured quality and latency — not a generic chatbot.

> Production-oriented, deployment-ready, observable, retrieval-transparent.
> What it is *not*: enterprise-scale, real-time analytics, or zero-hallucination — and it doesn't claim to be.

## Product at a glance

| Surface | Route | What it shows |
|---|---|---|
| Dashboard | `/` | Live corpus state + latest measured benchmark (from APIs/reports, never hard-coded) |
| Ask RAG | `/ask` | Grounded answers, confidence, clickable citations → evidence panel |
| Retrieval Explorer | `/retrieval` | Full pipeline trace: expansion, dense, BM25, fusion, rerank, final context + stage latency |
| Documents | `/documents` | Upload (drag & drop), search, inspect chunks, delete |
| Evaluation | `/evaluation` | 5-strategy ablation, metric selector, category analysis |
| Benchmarks | `/benchmark` | Background benchmark runner with live logs, latency tables, CSV exports |
| Failures | `/failures` | Ranking-divergence inspection (empty state when zero failures) |
| Monitoring | `/monitoring` | **Current session telemetry** (honestly labelled, process-local) |
| Settings | `/settings` | Read-only runtime config; secrets never reach the browser |

## Retrieval pipeline

1. **Query preprocessing** — normalization
2. **Query expansion** — LLM or local synonyms
3. **Dense retrieval** — Sentence-Transformers (`all-MiniLM-L6-v2`) + Qdrant
4. **Sparse retrieval** — BM25 persistent index
5. **Hybrid fusion** — RRF or weighted score
6. **CrossEncoder reranking** — `ms-marco-MiniLM-L-6-v2`
7. **Context construction** — dedup + budget fit
8. **Answer generation** — OpenAI-compatible LLM or `mock` demo provider, with citations

## Evaluation methodology

35 synthetic enterprise queries across categories (`exact_term, keyword, semantic,
acronym, multi_hop, hard`), K ∈ {1, 3, 5, 10}, metrics Precision/Recall/F1/MRR/NDCG/Hit-Rate,
five strategies ablated on the same query set. The benchmark uses **real Qdrant, real BM25,
real Sentence-Transformer, real CrossEncoder, real latency measurements**. Methodology was
not tuned for this pass — numbers below are the checked-in `reports/` artefacts, also served
live at `/api/reports/*`.

## Benchmark results (latest generated report)

| System | NDCG@5 | Recall@5 | Precision@5 | MRR |
|---|---|---|---|---|
| Dense | 0.9007 | 0.9429 | 0.1886 | 0.8857 |
| BM25 | 0.9218 | 0.9429 | 0.1886 | 0.9143 |
| Hybrid | 0.9323 | 0.9429 | 0.1886 | 0.9286 |
| Hybrid + Reranker | 0.9429 | 0.9429 | 0.1886 | 0.9429 |
| Hybrid + Expansion + Reranker | 0.9429 | 0.9429 | 0.1886 | 0.9429 |

## Latency (real measurements, CPU)

| System | Mean (ms) | P50 (ms) | P95 (ms) |
|---|---|---|---|
| Dense retrieval | 19.85 | 17.47 | 30.30 |
| BM25 retrieval | 0.30 | 0.29 | 0.34 |
| Hybrid retrieval | 3.78 | 3.58 | 5.95 |
| Hybrid + Reranker retrieval | 420.03 | 419.50 | 486.22 |
| Hybrid + Expansion + Reranker retrieval | 417.38 | 414.59 | 469.91 |

Takeaway: fusion adds single-digit milliseconds; the CrossEncoder dominates end-to-end latency (~420 ms p50 on CPU) and buys the NDCG@5 lift from 0.9323 → 0.9429.

## Failure analysis

Latest run: **0 failures / 175** — the Failures page renders an explicit empty state in that case and paginates real divergence records otherwise.

## Local setup

```bash
pip install -e ".[dev]"
docker compose up -d qdrant
make demo            # seed synthetic corpus (or: python -m scripts.seed_demo)
make run             # API on :8000
cd frontend && npm install && npm run dev   # UI on :5173 (proxies /api → :8000)
```

## Docker deployment

```bash
docker compose up --build                       # dev
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d   # prod overlay
```

Production image: non-root `appuser`, `HEALTHCHECK` on `/health`, persistent
`qdrant_data` + `model_cache` volumes, `unless-stopped` restarts, JSON log rotation.
Frontend ships as a static bundle (`frontend/Dockerfile`, nginx) configured at build
time via `VITE_API_BASE_URL`.

## Environment variables

See `.env.example`, `.env.development.example`, `.env.production.example`.
Key ones: `QDRANT_URL`, `EMBEDDING_MODEL`, `RERANKER_MODEL`, `DENSE/SPARSE/RERANK_TOP_K`,
`HYBRID_METHOD`, `HYBRID_ALPHA`, `QUERY_EXPANSION_ENABLED`, `LLM_PROVIDER` (`openai`|`mock`),
`LLM_MODEL`, `LLM_API_KEY` (never committed, never exposed via API), `CORS_ORIGINS`,
`RATE_LIMIT_*`, `MAX_UPLOAD_SIZE_MB`, and frontend `VITE_API_BASE_URL`.

## API

Full interactive docs at `/docs` (tags: System, health, documents, search, query, debug, evaluation).
Versioned aliases under `/api/v1/*` preserve existing consumers. Every response carries
`X-Request-ID`; retrieval responses also embed `request_id` in the body.

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/search -H 'Content-Type: application/json' -d '{"query": "SLA for P1?", "top_k": 5}'
curl -X POST http://localhost:8000/query  -H 'Content-Type: application/json' -d '{"query": "SLA for P1?", "top_k": 5}'
curl -X POST http://localhost:8000/debug/retrieval -H 'Content-Type: application/json' -d '{"query": "SLA for P1?"}'
curl http://localhost:8000/api/system/status
curl http://localhost:8000/api/monitoring/summary
```

## UI

`frontend/` — React + TypeScript + Vite + Tailwind. `npm run build` → `dist/`;
`npm run typecheck` for types. No secrets in the bundle; API endpoint via `VITE_API_BASE_URL`.

## Testing

```bash
make test            # pytest — 52 passed, 3 skipped (baseline preserved)
cd frontend && npm run build && npm run typecheck
```

## Deployment notes (any cloud)

Backend: any container host + managed Qdrant (or the composed one) + `LLM_PROVIDER=mock`
for keyless demos. Frontend: any static host with `VITE_API_BASE_URL` pointed at the API.
Health: `/health` (load-balancer) + `/api/system/status` (detail). See `docs/architecture.md`
for stores, lifecycle, and the deliberate no-persistent-monitoring decision.

## Known limitations

- Qdrant must be reachable for dense retrieval, upload indexing, and benchmarks (APIs degrade honestly with actionable messages).
- CrossEncoder reranking costs ~420 ms p50 on CPU; GPU or a smaller reranker changes the trade-off.
- Query expansion needs an OpenAI-compatible endpoint or falls back to local synonyms.
- Monitoring is session-local; benchmark job history is in-memory (reports persist to `reports/`).
- BM25 index is a local pickle file; document registry is aggregated from Qdrant at read time.

## Future improvements

- Streaming answer tokens (SSE) for long generations
- Persistent evaluation history DB + trend charts
- Redis-backed rate limiting for multi-replica deployments
- AuthN/Z (API keys / OIDC) for multi-tenant use
- GPU benchmark profile and reranker distillation experiments
