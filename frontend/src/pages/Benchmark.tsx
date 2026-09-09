import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { EmptyState, ErrorBox, LatencyBars, SectionTitle } from '../components/ui';

interface Job {
  job_id: string;
  status: string;
  params: Record<string, any>;
  elapsed_seconds: number;
  return_code?: number | null;
  error?: string | null;
  log_tail: string[];
}

export default function Benchmark() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<Array<Record<string, string>>>([]);
  const [form, setForm] = useState({ num_queries: 35, runs: 1, rebuild_index: false, device: '' });

  async function refreshJobs() {
    try {
      const r = await api<{ jobs: Job[] }>('/api/benchmark/jobs');
      setJobs(r.jobs);
      const running = r.jobs.find((j) => j.status === 'running' || j.status === 'queued') ?? null;
      setActive(running);
      return running;
    } catch {
      return null;
    }
  }

  useEffect(() => {
    refreshJobs();
    api<{ rows: Array<Record<string, string>> }>('/api/reports/latency').then((r) => setLatency(r.rows ?? [])).catch(() => {});
    const t = setInterval(refreshJobs, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const r = await api<{ job_id: string }>('/api/benchmark/run', {
        method: 'POST',
        body: JSON.stringify({
          num_queries: form.num_queries,
          runs: form.runs,
          rebuild_index: form.rebuild_index,
          device: form.device || null,
        }),
      });
      const j = await api<Job>(`/api/benchmark/jobs/${r.job_id}`);
      setActive(j);
      refreshJobs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Benchmarks</h1>
        <p className="mt-1 text-sm text-slate-500">
          Runs the real benchmark (Qdrant + BM25 + Sentence-Transformers + CrossEncoder) in the background. Reports land in <span className="font-mono">reports/</span>.
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle title="Run benchmark" hint="Requires Qdrant running" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-slate-600">
            Queries
            <input type="number" min={1} max={200} value={form.num_queries} onChange={(e) => setForm({ ...form, num_queries: Number(e.target.value) })} className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm" />
          </label>
          <label className="text-xs text-slate-600">
            Runs
            <input type="number" min={1} max={5} value={form.runs} onChange={(e) => setForm({ ...form, runs: Number(e.target.value) })} className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm" />
          </label>
          <label className="text-xs text-slate-600">
            Device
            <select value={form.device} onChange={(e) => setForm({ ...form, device: e.target.value })} className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm">
              <option value="">auto</option>
              <option value="cpu">cpu</option>
              <option value="cuda">cuda</option>
            </select>
          </label>
          <label className="flex items-end gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={form.rebuild_index} onChange={(e) => setForm({ ...form, rebuild_index: e.target.checked })} className="h-4 w-4" />
            Rebuild index
          </label>
        </div>
        <button onClick={start} disabled={starting || !!active} className="mt-3 rounded-md bg-blue-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50">
          {active ? 'Benchmark running…' : starting ? 'Starting…' : 'Run benchmark'}
        </button>
        {error && <div className="mt-2"><ErrorBox message={error} /></div>}
      </section>

      {active ? (
        <section className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="text-sm font-semibold text-blue-900" role="status">
            {active.status === 'queued' ? 'Queued…' : `Running… ${active.elapsed_seconds}s elapsed`}
          </div>
          <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-slate-900 p-3 font-mono text-xs text-slate-100" aria-label="Benchmark logs">
            {active.log_tail.join('\n') || 'Waiting for output…'}
          </pre>
        </section>
      ) : (
        jobs.length === 0 && <EmptyState title="No benchmark jobs yet" body="Configure a run above. Progress and logs stream here while it executes." />
      )}

      {jobs.length > 0 && (
        <section>
          <SectionTitle title="Job history" />
          <div className="space-y-2">
            {jobs.map((j) => (
              <div key={j.job_id} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm shadow-sm">
                <span className="font-mono text-xs font-semibold">{j.job_id}</span>
                <span className="ml-2 text-xs text-slate-500">{j.status}{j.return_code != null ? ` (exit ${j.return_code})` : ''}</span>
                {j.error && <p className="mt-1 text-xs text-red-600">{j.error}</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      {latency.length > 0 && (
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle title="Measured latency by stage" hint="From the latest latency report (real measurements)" />
          <LatencyBars stages={Object.fromEntries(latency.slice(0, 12).map((r) => [`${r.method ?? ''}.${r.stage ?? ''}`, Number(r.p50_ms ?? r.mean_ms ?? 0)]))} />
          <div className="table-scroll mt-3">
            <table className="w-full min-w-[560px] text-left font-mono text-xs">
              <thead>
                <tr className="text-slate-500">
                  {Object.keys(latency[0]).map((k) => (
                    <th key={k} className="px-3 py-1 font-medium">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {latency.map((r, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {Object.values(r).map((v, j) => (
                      <td key={j} className="px-3 py-1">{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {['benchmark', 'ablation', 'latency', 'category'].map((k) => (
              <a key={k} href={`/api/reports/export?kind=${k}`} className="rounded border border-slate-300 px-2 py-1 font-medium text-slate-600 hover:border-blue-400 hover:text-blue-700" download>
                Export {k}.csv
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
