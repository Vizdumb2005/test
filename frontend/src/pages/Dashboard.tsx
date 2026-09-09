import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { EmptyState, ErrorBox, MetricCard, SectionTitle, Skeleton } from '../components/ui';

interface BenchmarkData {
  generated_at: string;
  summary: Record<string, Record<string, number>>;
}

const num = (v: unknown, d = 4) => (typeof v === 'number' ? v.toFixed(d) : '—');

export default function Dashboard() {
  const [bench, setBench] = useState<BenchmarkData | null>(null);
  const [latency, setLatency] = useState<Record<string, any> | null>(null);
  const [docCount, setDocCount] = useState<number | null>(null);
  const [chunkCount, setChunkCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [b, l, d] = await Promise.all([
          api<{ data: BenchmarkData }>('/api/reports/benchmark').catch(() => null),
          api<{ raw: any }>('/api/reports/latency').catch(() => null),
          api<{ total: number; documents: Array<{ chunk_count: number }> }>('/api/documents/index?page_size=100').catch(() => null),
        ]);
        if (!alive) return;
        if (b) setBench(b.data);
        if (l?.raw?.latency) setLatency(l.raw.latency);
        if (d) {
          setDocCount(d.total);
          setChunkCount(d.documents.reduce((a, x) => a + (x.chunk_count ?? 0), 0));
        }
      } catch (e: any) {
        if (alive) setError(e.message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const best = useMemo(() => {
    if (!bench?.summary) return null;
    let out = { method: '', ndcg: 0, recall: 0, mrr: 0 };
    for (const [method, m] of Object.entries(bench.summary)) {
      const ndcg = m['ndcg@5'] ?? 0;
      if (ndcg >= out.ndcg) out = { method, ndcg, recall: m['recall@5'] ?? 0, mrr: m['mrr'] ?? 0 };
    }
    return out;
  }, [bench]);

  const rerank = latency?.['hybrid+reranker.retrieval'];

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }
  if (error) return <ErrorBox message={error} retry={() => location.reload()} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Live index state plus the latest measured benchmark. All figures come from backend APIs and generated reports — nothing is hard-coded.
        </p>
      </div>

      {!bench && (
        <EmptyState
          title="No benchmark data yet"
          body="Run the benchmark to populate quality and latency metrics. The dashboard will fill in automatically."
          action={<Link to="/benchmark" className="rounded-md bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800">Open Benchmarks</Link>}
        />
      )}

      <section aria-label="Corpus">
        <SectionTitle title="Corpus" hint="Current Qdrant / BM25 index state" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Documents" value={docCount !== null ? String(docCount) : '—'} sub="indexed in Qdrant" />
          <MetricCard label="Chunks" value={chunkCount !== null ? chunkCount.toLocaleString() : '—'} sub="retrievable units" />
          <MetricCard label="Best method" value={best?.method ?? '—'} sub={bench ? `generated ${new Date(bench.generated_at).toLocaleString()}` : undefined} />
          <MetricCard label="Rerank p50" value={rerank?.p50 != null ? `${Math.round(rerank.p50)} ms` : '—'} sub="hybrid+reranker retrieval" />
        </div>
      </section>

      {best && (
        <section aria-label="Quality">
          <SectionTitle title="Retrieval quality" hint={`Best configuration: ${best.method}`} />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Best NDCG@5" value={num(best.ndcg)} />
            <MetricCard label="Best Recall@5" value={num(best.recall)} />
            <MetricCard label="Best MRR" value={num(best.mrr)} />
            <MetricCard label="Rerank p95" value={rerank?.p95 != null ? `${Math.round(rerank.p95)} ms` : '—'} sub={rerank?.p50 != null ? `p50 ${Math.round(rerank.p50)} ms` : 'measured end-to-end'} />
          </div>
        </section>
      )}

      <section aria-label="Navigate">
        <SectionTitle title="Workflows" />
        <div className="grid gap-3 md:grid-cols-3">
          {[
            { to: '/ask', t: 'Ask a question', d: 'Query the knowledge base and inspect cited evidence.' },
            { to: '/retrieval', t: 'Trace retrieval', d: 'Expand every stage: expansion, dense, BM25, fusion, rerank.' },
            { to: '/failures', t: 'Study failures', d: 'See exactly where ranking diverged on hard queries.' },
          ].map((c) => (
            <Link key={c.to} to={c.to} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-300 hover:shadow">
              <div className="text-sm font-semibold text-blue-800">{c.t}</div>
              <p className="mt-1 text-sm text-slate-500">{c.d}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
