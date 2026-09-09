import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { ErrorBox, SectionTitle } from '../components/ui';

export default function Settings() {
  const [cfg, setCfg] = useState<{ runtime: Record<string, any>; environment: Record<string, any>; note: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ runtime: Record<string, any>; environment: Record<string, any>; note: string }>('/api/config/public')
      .then(setCfg)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} retry={() => location.reload()} />;
  if (!cfg) return <p className="text-sm text-slate-500">Loading configuration…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Read-only view of live server configuration. Secrets are never exposed to the browser.</p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle title="Runtime configuration" hint="Search behavior (restart required to change via environment)" />
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {Object.entries(cfg.runtime).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between border-b border-slate-100 py-1.5 text-sm">
              <dt className="font-mono text-xs text-slate-500">{k}</dt>
              <dd className="font-mono text-xs font-medium text-slate-800">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle title="Environment configuration" hint="Deployment-level settings" />
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {Object.entries(cfg.environment).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between border-b border-slate-100 py-1.5 text-sm">
              <dt className="font-mono text-xs text-slate-500">{k}</dt>
              <dd className="font-mono text-xs font-medium text-slate-800">{String(v)}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-500">{cfg.note}</p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Key variables</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-xs">
          <li>LLM_PROVIDER=mock — keyless demo mode (real retrieval, deterministic answers)</li>
          <li>LLM_PROVIDER=openai + LLM_API_KEY — grounded generation via OpenAI-compatible API</li>
          <li>HYBRID_METHOD=rrf|weighted, HYBRID_ALPHA, DENSE_TOP_K, SPARSE_TOP_K, RERANK_TOP_K</li>
          <li>VITE_API_BASE_URL — frontend API endpoint (build-time)</li>
        </ul>
      </section>
    </div>
  );
}
