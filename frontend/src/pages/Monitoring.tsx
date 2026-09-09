import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { ErrorBox, MetricCard, SectionTitle } from '../components/ui';

interface Summary {
  scope: string;
  note: string;
  uptime_seconds: number;
  total_requests: number;
  total_errors: number;
  error_rate: number;
  endpoints: Record<string, { requests: number; errors: number; mean_ms?: number | null; p50_ms?: number | null; p95_ms?: number | null }>;
  retrieval_stages: Record<string, { count: number; mean_ms?: number | null; p50_ms?: number | null; p95_ms?: number | null }>;
  recent_requests: Array<{ request_id: string; endpoint: string; status: number; duration_ms: number }>;
}

export default function Monitoring() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const r = await api<Summary>('/api/monitoring/summary');
        if (alive) setData(r);
      } catch (e: any) {
        if (alive) setError(e.message);
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (error) return <ErrorBox message={error} retry={() => location.reload()} />;
  if (!data) return <p className="text-sm text-slate-500">Loading session telemetry…</p>;

  const eps = Object.entries(data.endpoints);
  const maxP95 = Math.max(1, ...eps.map(([, v]) => v.p95_ms ?? 0));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Monitoring</h1>
        <p className="mt-1 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
          Current session telemetry — process-local counters for this API instance. Resets on restart; not a persistent production monitoring system.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Requests" value={String(data.total_requests)} sub={`uptime ${Math.round(data.uptime_seconds)}s`} />
        <MetricCard label="Errors" value={String(data.total_errors)} sub={`rate ${(data.error_rate * 100).toFixed(2)}%`} />
        <MetricCard label="Endpoints tracked" value={String(eps.length)} />
        <MetricCard label="Retrieval stages" value={String(Object.keys(data.retrieval_stages).length)} />
      </div>

      <section>
        <SectionTitle title="Latency by endpoint (p95)" />
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          {eps.length === 0 && <p className="text-sm text-slate-500">No requests recorded yet — ask a question or run a trace.</p>}
          <div className="space-y-2">
            {eps.map(([ep, v]) => (
              <div key={ep} className="grid grid-cols-[1fr_80px] items-center gap-2 text-sm">
                <div>
                  <span className="font-mono text-xs text-slate-700">{ep}</span>
                  <span className="ml-2 text-xs text-slate-400">{v.requests} req · {v.errors} err</span>
                  <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100">
                    <div className="h-full rounded bg-blue-600" style={{ width: `${Math.min(100, ((v.p95_ms ?? 0) / maxP95) * 100)}%` }} />
                  </div>
                </div>
                <span className="text-right font-mono text-xs">{v.p95_ms != null ? `${Math.round(v.p95_ms)} ms` : '—'}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <SectionTitle title="Retrieval stage counts" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(data.retrieval_stages).map(([s, v]) => (
            <MetricCard key={s} label={s} value={String(v.count)} sub={v.p50_ms != null ? `p50 ${Math.round(v.p50_ms)} ms · p95 ${Math.round(v.p95_ms ?? 0)} ms` : undefined} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle title="Recent requests" />
        <div className="table-scroll rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[560px] text-left font-mono text-xs">
            <thead>
              <tr className="text-slate-500">
                <th className="px-4 py-2 font-medium">Request ID</th>
                <th className="px-4 py-2 font-medium">Endpoint</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_requests.map((r) => (
                <tr key={r.request_id} className="border-t border-slate-100">
                  <td className="px-4 py-1.5">{r.request_id}</td>
                  <td className="px-4 py-1.5">{r.endpoint}</td>
                  <td className="px-4 py-1.5">{r.status}</td>
                  <td className="px-4 py-1.5">{r.duration_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
