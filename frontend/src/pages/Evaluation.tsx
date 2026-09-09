import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { EmptyState, ErrorBox, MetricCard, SectionTitle } from '../components/ui';

const METHODS = ['dense_only', 'bm25_only', 'hybrid', 'hybrid+reranker', 'hybrid+expansion+reranker'];
const METRICS = ['ndcg@5', 'recall@5', 'precision@5', 'mrr', 'hit_rate@5'];

function barColor(i: number) {
  return ['bg-slate-400', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-600', 'bg-violet-600'][i % 5];
}

export default function Evaluation() {
  const [summary, setSummary] = useState<Record<string, Record<string, number>> | null>(null);
  const [metric, setMetric] = useState('ndcg@5');
  const [category, setCategory] = useState<Array<Record<string, string>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [b, c] = await Promise.all([
          api<{ data: { summary: Record<string, Record<string, number>> } }>('/api/reports/benchmark').catch(() => null),
          api<{ rows: Array<Record<string, string>> }>('/api/reports/category').catch(() => null),
        ]);
        if (!alive) return;
        if (b) setSummary(b.data.summary);
        if (c) setCategory(c.rows);
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

  const maxVal = useMemo(() => {
    if (!summary) return 1;
    return Math.max(0.01, ...METHODS.map((m) => summary[m]?.[metric] ?? 0));
  }, [summary, metric]);

  if (loading) return <p className="text-sm text-slate-500">Loading evaluation…</p>;
  if (error) return <ErrorBox message={error} retry={() => location.reload()} />;
  if (!summary) {
    return (
      <EmptyState
        title="No evaluation runs yet"
        body="Run the benchmark to generate precision, recall, NDCG, MRR and hit-rate metrics across all five retrieval strategies."
      />
    );
  }

  const present = METHODS.filter((m) => summary[m]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Evaluation</h1>
        <p className="mt-1 text-sm text-slate-500">Measured retrieval quality at K = 1, 3, 5, 10. Source: generated benchmark reports.</p>
      </div>

      <section>
        <SectionTitle
          title="Ablation comparison"
          hint="Five retrieval strategies on the same query set"
          right={
            <label className="text-xs text-slate-600">
              Metric:{' '}
              <select value={metric} onChange={(e) => setMetric(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-sm" aria-label="Select metric">
                {METRICS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
          }
        />
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="space-y-2">
            {present.map((m, i) => (
              <div key={m} className="grid grid-cols-[220px_1fr_70px] items-center gap-2 text-sm">
                <span className="truncate font-mono text-xs text-slate-700" title={m}>{m}</span>
                <div className="h-3 overflow-hidden rounded bg-slate-100">
                  <div className={`h-full rounded ${barColor(i)}`} style={{ width: `${((summary[m]?.[metric] ?? 0) / maxVal) * 100}%` }} />
                </div>
                <span className="text-right font-mono text-xs">{(summary[m]?.[metric] ?? 0).toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <SectionTitle title="Metric cards" hint="Selected metric per strategy" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {present.map((m) => (
            <MetricCard key={m} label={m} value={(summary[m]?.[metric] ?? 0).toFixed(4)} sub={metric} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle title="Full comparison table" hint="All headline metrics" />
        <div className="table-scroll rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead>
              <tr className="text-slate-500">
                <th className="px-4 py-2 font-medium">Method</th>
                {METRICS.map((m) => (
                  <th key={m} className="px-4 py-2 font-medium">{m}</th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono">
              {present.map((m) => (
                <tr key={m} className="border-t border-slate-100">
                  <td className="px-4 py-2">{m}</td>
                  {METRICS.map((k) => (
                    <td key={k} className="px-4 py-2">{(summary[m]?.[k] ?? 0).toFixed(4)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {category.length > 0 && (
        <section>
          <SectionTitle title="Performance by query category" hint="Where each strategy wins or loses" />
          <div className="table-scroll rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead>
                <tr className="text-slate-500">
                  {Object.keys(category[0]).map((k) => (
                    <th key={k} className="px-4 py-2 font-medium">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {category.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {Object.values(row).map((v, j) => (
                      <td key={j} className="px-4 py-2">{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
