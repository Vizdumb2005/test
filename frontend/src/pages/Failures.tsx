import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Badge, EmptyState, ErrorBox } from '../components/ui';

interface Failure {
  query?: string;
  category?: string;
  failure_type?: string;
  expected_chunk?: string;
  actual_top?: string;
  [k: string]: any;
}

export default function Failures() {
  const [failures, setFailures] = useState<Failure[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  async function load(p: number) {
    setLoading(true);
    try {
      const r = await api<{ total: number; page: number; failures: Failure[] }>(`/api/reports/failures?page=${p}&page_size=${pageSize}`);
      setFailures(r.failures);
      setTotal(r.total);
      setPage(r.page);
      setSelected(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return <p className="text-sm text-slate-500">Loading failure analysis…</p>;
  if (error) return <ErrorBox message={error} retry={() => load(page)} />;
  if (total === 0) {
    return (
      <EmptyState
        title="No failures recorded"
        body="Either the benchmark found no ranking failures, or no failure analysis has been generated yet. Run a benchmark to populate this view."
      />
    );
  }

  const sel = selected !== null ? failures[selected] : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Failure Analysis</h1>
        <p className="mt-1 text-sm text-slate-500">{total} queries where ranking diverged. Select one to see where dense, BM25, hybrid and reranker disagreed.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="table-scroll rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead>
              <tr className="text-slate-500">
                <th className="px-4 py-2 font-medium">Query</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Failure type</th>
              </tr>
            </thead>
            <tbody>
              {failures.map((f, i) => (
                <tr key={i} className={`border-t border-slate-100 ${selected === i ? 'bg-blue-50' : ''}`}>
                  <td className="px-4 py-2">
                    <button onClick={() => setSelected(i)} className="text-left font-medium text-blue-700 hover:underline">
                      {String(f.query ?? `failure ${i + 1}`)}
                    </button>
                  </td>
                  <td className="px-4 py-2">{f.category ? <Badge>{String(f.category)}</Badge> : '—'}</td>
                  <td className="px-4 py-2">{f.failure_type ? <Badge tone="amber">{String(f.failure_type)}</Badge> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <aside className="xl:sticky xl:top-16 xl:self-start">
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Divergence detail</h2>
            {!sel && <p className="mt-2 text-slate-500">Select a failure to inspect expected vs actual ranking.</p>}
            {sel && (
              <dl className="mt-2 space-y-2 text-xs">
                {Object.entries(sel).map(([k, v]) => (
                  <div key={k}>
                    <dt className="font-mono font-semibold text-slate-500">{k}</dt>
                    <dd className="mt-0.5 break-words text-slate-700">
                      {typeof v === 'object' ? <pre className="overflow-auto rounded bg-slate-50 p-2 font-mono text-[11px]">{JSON.stringify(v, null, 2)}</pre> : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </aside>
      </div>
      {total > pageSize && (
        <div className="flex items-center gap-2 text-sm">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="rounded border px-2 py-1 disabled:opacity-40">← Prev</button>
          <span className="text-slate-600">Page {page} of {Math.ceil(total / pageSize)}</span>
          <button disabled={page >= Math.ceil(total / pageSize)} onClick={() => load(page + 1)} className="rounded border px-2 py-1 disabled:opacity-40">Next →</button>
        </div>
      )}
    </div>
  );
}
