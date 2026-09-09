import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import { ErrorBox } from '../components/ui';

interface Chunk {
  chunk_id: string;
  chunk_index: number;
  page_number?: number | null;
  section?: string | null;
  text: string;
}

export default function DocDetail() {
  const { id } = useParams<{ id: string }>();
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load(p: number) {
    setLoading(true);
    try {
      const r = await api<{ chunk_count: number; total: number; page: number; chunks: Chunk[] }>(
        `/api/documents/index/${encodeURIComponent(id ?? '')}?page=${p}&page_size=20`,
      );
      setChunks(r.chunks);
      setTotal(r.total);
      setPage(r.page);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <div className="space-y-4">
      <Link to="/documents" className="text-sm font-medium text-blue-700 hover:underline">
        ← Back to Documents
      </Link>
      <div>
        <h1 className="break-all font-mono text-lg font-semibold text-slate-900">{id}</h1>
        <p className="mt-1 text-sm text-slate-500">{total} indexed chunks. Inspect exactly what the retriever sees.</p>
      </div>
      {error && <ErrorBox message={error} retry={() => load(page)} />}
      {loading ? (
        <p className="text-sm text-slate-500">Loading chunks…</p>
      ) : (
        <ol className="space-y-2">
          {chunks.map((c) => (
            <li key={c.chunk_id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm">
              <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs text-slate-500">
                <span className="font-semibold text-slate-700">#{c.chunk_index}</span>
                <span className="break-all">{c.chunk_id}</span>
                {c.page_number != null && <span>page {c.page_number}</span>}
                {c.section && <span>§ {c.section}</span>}
              </div>
              <p className="mt-1 text-slate-700">{c.text}</p>
            </li>
          ))}
        </ol>
      )}
      {total > 20 && (
        <div className="flex items-center gap-2 text-sm">
          <button disabled={page <= 1} onClick={() => load(page - 1)} className="rounded border px-2 py-1 disabled:opacity-40">← Prev</button>
          <span className="text-slate-600">Page {page} of {Math.ceil(total / 20)}</span>
          <button disabled={page >= Math.ceil(total / 20)} onClick={() => load(page + 1)} className="rounded border px-2 py-1 disabled:opacity-40">Next →</button>
        </div>
      )}
    </div>
  );
}
