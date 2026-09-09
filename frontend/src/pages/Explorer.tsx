import { useState } from 'react';
import { api, type DebugResponse } from '../lib/api';
import { Badge, EmptyState, ErrorBox, LatencyBars } from '../components/ui';

function StageTable(props: { title: string; rows: Array<Record<string, any>>; scoreKey?: string }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left"
      >
        <span className="text-sm font-semibold text-slate-800">
          {props.title} <span className="ml-1 font-mono text-xs text-slate-400">{props.rows.length}</span>
        </span>
        <span className="text-slate-400" aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="table-scroll border-t border-slate-100">
          {props.rows.length === 0 ? (
            <p className="px-4 py-3 text-sm text-slate-500">No results at this stage.</p>
          ) : (
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead>
                <tr className="text-slate-500">
                  <th className="px-4 py-2 font-medium">Rank</th>
                  <th className="px-4 py-2 font-medium">Chunk</th>
                  <th className="px-4 py-2 font-medium">Score</th>
                  <th className="px-4 py-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {props.rows.map((r, i) => (
                  <tr key={String(r.chunk_id ?? i)} className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono">{r.rank ?? i + 1}</td>
                    <td className="max-w-[420px] truncate px-4 py-2 font-mono text-slate-600" title={String(r.chunk_id ?? '')}>
                      {String(r.chunk_id ?? '—')}
                    </td>
                    <td className="px-4 py-2 font-mono">{typeof r.score === 'number' ? r.score.toFixed(4) : '—'}</td>
                    <td className="max-w-[220px] truncate px-4 py-2 text-slate-600" title={String(r.metadata?.file_name ?? r.document_id ?? '')}>
                      {String(r.metadata?.file_name ?? r.document_id ?? '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default function Explorer() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DebugResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api<DebugResponse>('/debug/retrieval', { method: 'POST', body: JSON.stringify({ query: q, top_k: 10 }) });
      setData(r);
    } catch (e: any) {
      setError(e.message ?? 'Debug retrieval failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Retrieval Explorer</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every stage of the hybrid pipeline for one query — query expansion, dense and BM25 retrieval, fusion, CrossEncoder reranking, final context.
        </p>
      </div>

      <div className="flex gap-2">
        <label htmlFor="exq" className="sr-only">Query to trace</label>
        <input
          id="exq"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && run()}
          placeholder="Enter a query to trace through the pipeline…"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500"
        />
        <button onClick={run} disabled={loading || !query.trim()} className="rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50">
          {loading ? 'Tracing…' : 'Trace'}
        </button>
      </div>

      {error && <ErrorBox message={error} retry={run} />}
      {!data && !error && <EmptyState title="No trace yet" body="Run a query to see how it flows from expansion to reranked context." />}

      {data && (
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <div className="font-medium text-slate-800">Original query</div>
            <p className="mt-1 text-slate-700">{data.query}</p>
            <div className="mt-2 font-medium text-slate-800">Expanded queries</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {data.expanded_queries.length === 0 && <span className="text-xs text-slate-500">Expansion disabled or no expansions.</span>}
              {data.expanded_queries.map((q, i) => (
                <Badge key={i} tone="blue">{q}</Badge>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-700">Stage latency</h2>
            <LatencyBars stages={data.latency_ms} />
          </div>

          <StageTable title="Dense retrieval (Qdrant + Sentence-Transformers)" rows={data.dense_results} />
          <StageTable title="Sparse retrieval (BM25)" rows={data.sparse_results} />
          <StageTable title="Hybrid fusion (RRF / weighted)" rows={data.fusion_results} />
          <StageTable title="CrossEncoder reranked" rows={data.reranked_results} />
          <StageTable title="Final context (LLM input)" rows={data.final_context} />
        </div>
      )}
    </div>
  );
}
