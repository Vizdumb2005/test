import React from 'react';

export function MetricCard(props: { label: string; value: string; sub?: string; title?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm" title={props.title}>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{props.label}</div>
      <div className="mt-1 font-mono text-2xl font-semibold text-slate-900">{props.value}</div>
      {props.sub && <div className="mt-0.5 text-xs text-slate-500">{props.sub}</div>}
    </div>
  );
}

export function StatusDot(props: { status: string }) {
  const color =
    props.status === 'operational'
      ? 'bg-emerald-500'
      : props.status === 'degraded'
        ? 'bg-amber-500'
        : 'bg-red-500';
  return (
    <span className="inline-flex items-center gap-1.5" role="status" aria-label={`status ${props.status}`}>
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} aria-hidden="true" />
      <span className="text-xs font-medium capitalize text-slate-600">{props.status}</span>
    </span>
  );
}

export function EmptyState(props: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <div className="text-sm font-semibold text-slate-800">{props.title}</div>
      <p className="mt-1 max-w-md text-sm text-slate-500">{props.body}</p>
      {props.action && <div className="mt-4">{props.action}</div>}
    </div>
  );
}

export function Skeleton(props: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-slate-200 ${props.className ?? 'h-4 w-full'}`} />;
}

export function SectionTitle(props: { title: string; hint?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">{props.title}</h2>
        {props.hint && <p className="mt-0.5 text-xs text-slate-500">{props.hint}</p>}
      </div>
      {props.right}
    </div>
  );
}

export function Badge(props: { children: React.ReactNode; tone?: 'slate' | 'blue' | 'green' | 'amber' | 'red' }) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[props.tone ?? 'slate']}`}>
      {props.children}
    </span>
  );
}

export function LatencyBars(props: { stages: Record<string, number>; maxMs?: number }) {
  const entries = Object.entries(props.stages).filter(([, v]) => typeof v === 'number');
  const max = props.maxMs ?? Math.max(1, ...entries.map(([, v]) => v));
  if (entries.length === 0) return <p className="text-sm text-slate-500">No latency data.</p>;
  return (
    <div className="space-y-2" role="table" aria-label="Latency by stage">
      {entries.map(([stage, ms]) => (
        <div key={stage} className="grid grid-cols-[140px_1fr_80px] items-center gap-2 text-sm" role="row">
          <span className="truncate font-mono text-xs text-slate-600" title={stage}>
            {stage}
          </span>
          <div className="h-2.5 overflow-hidden rounded bg-slate-100">
            <div
              className="h-full rounded bg-blue-600 transition-[width]"
              style={{ width: `${Math.max(2, Math.min(100, (ms / max) * 100))}%` }}
            />
          </div>
          <span className="text-right font-mono text-xs text-slate-700">{ms < 10 ? ms.toFixed(1) : Math.round(ms)} ms</span>
        </div>
      ))}
    </div>
  );
}

export function ErrorBox(props: { message: string; requestId?: string | null; retry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      <div className="font-semibold">Something went wrong</div>
      <p className="mt-1">{props.message}</p>
      {props.requestId && (
        <p className="mt-1 font-mono text-xs text-red-600">Request ID: {props.requestId} — include it when reporting issues.</p>
      )}
      {props.retry && (
        <button
          onClick={props.retry}
          className="mt-2 rounded-md border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Retry
        </button>
      )}
    </div>
  );
}
