import { useState } from 'react';
import { api, type QueryResponse } from '../lib/api';
import { Badge, EmptyState, ErrorBox, LatencyBars } from '../components/ui';

const EXAMPLES = [
  'What is the SLA for P1 incidents?',
  'What happens when an invoice becomes overdue?',
  'How long are audit logs retained?',
  'How should a severity-1 incident be escalated?',
];

const STAGES = ['Analyzing query…', 'Searching knowledge base…', 'Reranking evidence…', 'Generating answer…'];

function renderAnswerWithCitations(answer: string, citations: Array<Record<string, any>>, onCite: (i: number) => void) {
  // Highlight [n] markers and make them clickable.
  const parts = answer.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    if (m) {
      const idx = Number(m[1]) - 1;
      if (idx >= 0 && idx < citations.length) {
        return (
          <button
            key={i}
            onClick={() => onCite(idx)}
            className="mx-0.5 rounded bg-blue-50 px-1 font-mono text-xs font-semibold text-blue-700 underline decoration-blue-300 hover:bg-blue-100"
            aria-label={`Open evidence ${m[1]}`}
          >
            {p}
          </button>
        );
      }
    }
    return <span key={i}>{p}</span>;
  });
}

export default function Ask() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<{ message: string; requestId: string | null } | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  async function submit(q?: string) {
    const text = (q ?? query).trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setSelected(null);
    const timer = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 900);
    try {
      const r = await api<QueryResponse>('/query', { method: 'POST', body: JSON.stringify({ query: text, top_k: 8 }) });
      setResult(r);
    } catch (e: any) {
      setError({ message: e.message ?? 'Query failed', requestId: e.requestId ?? null });
    } finally {
      clearInterval(timer);
      setLoading(false);
      setStage(0);
    }
  }

  const evidence = selected !== null ? result?.retrieval_results[selected] : undefined;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Ask RAG</h1>
        <p className="mt-1 text-sm text-slate-500">Grounded answers with clickable citations into retrieved evidence.</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label htmlFor="q" className="sr-only">
          Ask a question
        </label>
        <textarea
          id="q"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask about your enterprise knowledge base… (Enter to submit, Shift+Enter for newline)"
          className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            onClick={() => submit()}
            disabled={loading || !query.trim()}
            className="rounded-md bg-blue-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {loading ? 'Searching…' : 'Ask'}
          </button>
          {loading && (
            <span className="text-sm text-slate-500" role="status">
              {STAGES[stage]}
            </span>
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Example prompts">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuery(ex);
                submit(ex);
              }}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:border-blue-300 hover:text-blue-700"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBox message={error.message} requestId={error.requestId} retry={() => submit()} />}

      {!result && !loading && !error && (
        <EmptyState title="No question asked yet" body="Type a question above or try an example prompt. Answers always cite the chunks they were built from." />
      )}

      {result && (
        <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Answer</h2>
                <Badge tone={result.confidence >= 0.6 ? 'green' : 'amber'}>
                  confidence {(result.confidence * 100).toFixed(0)}%
                </Badge>
                {result.request_id && <span className="ml-auto font-mono text-xs text-slate-400">{result.request_id}</span>}
              </div>
              <div className="mt-2 text-sm leading-relaxed text-slate-800">
                {renderAnswerWithCitations(result.answer, result.citations, setSelected)}
              </div>
              {result.retrieval_results.length === 0 && (
                <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  No relevant chunks found. The answer is explicitly marked as unknown rather than hallucinated.
                </p>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Sources</h2>
              <ol className="mt-2 space-y-2">
                {result.retrieval_results.slice(0, 8).map((r, i) => (
                  <li key={r.chunk_id}>
                    <button
                      onClick={() => setSelected(i)}
                      className={`block w-full rounded-md border px-3 py-2 text-left text-sm hover:border-blue-300 ${
                        selected === i ? 'border-blue-400 bg-blue-50' : 'border-slate-200'
                      }`}
                      aria-label={`Open evidence for source ${i + 1}`}
                    >
                      <span className="font-mono text-xs font-semibold text-blue-700">[{i + 1}]</span>{' '}
                      <span className="font-medium text-slate-800">{r.metadata?.file_name ?? r.document_id}</span>
                      <span className="ml-2 font-mono text-xs text-slate-500">score {r.score.toFixed(3)}</span>
                      <span className="ml-2 text-xs text-slate-400">{r.retrieval_method}</span>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-500">{r.text}</p>
                    </button>
                  </li>
                ))}
              </ol>
            </div>

            {result.latency_ms && Object.keys(result.latency_ms).length > 0 && (
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-700">Pipeline latency</h2>
                <LatencyBars stages={result.latency_ms} />
              </div>
            )}
          </div>

          {/* Evidence panel */}
          <aside aria-label="Evidence" className="xl:sticky xl:top-16 xl:self-start">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Evidence</h2>
              {!evidence && <p className="mt-2 text-sm text-slate-500">Select a citation or source to inspect the exact retrieved chunk.</p>}
              {evidence && (
                <div className="mt-2 space-y-2 text-sm">
                  <div className="font-mono text-xs font-semibold text-blue-700">Evidence #{(selected ?? 0) + 1}</div>
                  <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-xs">
                    <dt className="text-slate-500">Document</dt>
                    <dd className="break-all font-medium text-slate-800">{evidence.metadata?.file_name ?? evidence.document_id}</dd>
                    <dt className="text-slate-500">Page</dt>
                    <dd>{evidence.metadata?.page_number ?? '—'}</dd>
                    <dt className="text-slate-500">Section</dt>
                    <dd>{evidence.metadata?.section ?? '—'}</dd>
                    <dt className="text-slate-500">Chunk ID</dt>
                    <dd className="break-all font-mono">{evidence.chunk_id}</dd>
                    <dt className="text-slate-500">Score</dt>
                    <dd className="font-mono">{evidence.score.toFixed(4)}</dd>
                    <dt className="text-slate-500">Method</dt>
                    <dd>{evidence.retrieval_method}</dd>
                  </dl>
                  <blockquote className="rounded-md border-l-2 border-blue-400 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
                    {evidence.text}
                  </blockquote>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
