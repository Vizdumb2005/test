import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, apiBase } from '../lib/api';
import { Badge, EmptyState, ErrorBox, SectionTitle } from '../components/ui';

interface DocEntry {
  document_id: string;
  file_name: string;
  source: string;
  document_type: string;
  chunk_count: number;
  page_count: number;
  status: string;
}

export default function Documents() {
  const [docs, setDocs] = useState<DocEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (p: number, query: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await api<{ total: number; documents: DocEntry[] }>(
        `/api/documents/index?page=${p}&page_size=20${query ? `&q=${encodeURIComponent(query)}` : ''}`,
      );
      setDocs(r.documents);
      setTotal(r.total);
      setPage(p);
    } catch (e: any) {
      setError(e.message ?? 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(1, '');
  }, [load]);

  async function upload(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      for (const f of list) {
        const form = new FormData();
        form.append('file', f);
        const res = await fetch(`${apiBase}/documents/upload`, { method: 'POST', body: form });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `Upload failed for ${f.name}`);
        }
      }
      setNotice(`Uploaded ${list.length} file(s) and indexed successfully.`);
      await load(1, q);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function remove(id: string) {
    if (!confirm(`Delete document ${id} from the index?`)) return;
    try {
      await api(`/api/documents/index/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setNotice(`Deleted ${id}.`);
      await load(page, q);
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Documents</h1>
        <p className="mt-1 text-sm text-slate-500">Upload, search, inspect and delete indexed documents.</p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          upload(e.dataTransfer.files);
        }}
        className={`rounded-lg border-2 border-dashed px-6 py-6 text-center ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-slate-300 bg-white'}`}
      >
        <p className="text-sm font-medium text-slate-700">Drag & drop files here, or</p>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="mt-2 rounded-md bg-blue-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
        >
          {uploading ? 'Indexing…' : 'Browse files'}
        </button>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx"
          className="hidden"
          onChange={(e) => e.target.files && upload(e.target.files)}
          aria-label="Upload documents"
        />
        <p className="mt-2 text-xs text-slate-500">PDF, TXT, Markdown, DOCX. Filenames are sanitized server-side.</p>
      </div>

      {notice && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{notice}</div>}
      {error && <ErrorBox message={error} retry={() => load(page, q)} />}

      <div>
        <SectionTitle
          title={`Index (${total})`}
          right={
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                load(1, e.target.value);
              }}
              placeholder="Search documents…"
              aria-label="Search documents"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            />
          }
        />
        {loading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : docs.length === 0 ? (
          <EmptyState
            title="No documents indexed"
            body="Upload your first document above, or seed the demo corpus with `make demo`. The knowledge base starts working immediately after ingestion."
          />
        ) : (
          <div className="table-scroll rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="text-xs text-slate-500">
                  <th className="px-4 py-2 font-medium">File</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Chunks</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.document_id} className="border-t border-slate-100">
                    <td className="px-4 py-2">
                      <Link to={`/documents/${encodeURIComponent(d.document_id)}`} className="font-medium text-blue-700 hover:underline">
                        {d.file_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-slate-600">{d.document_type}</td>
                    <td className="px-4 py-2 font-mono">{d.chunk_count}</td>
                    <td className="px-4 py-2">
                      <Badge tone="green">{d.status}</Badge>
                    </td>
                    <td className="px-4 py-2">
                      <button onClick={() => remove(d.document_id)} className="text-xs font-medium text-red-600 hover:underline">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 20 && (
          <div className="mt-2 flex items-center gap-2 text-sm">
            <button disabled={page <= 1} onClick={() => load(page - 1, q)} className="rounded border px-2 py-1 disabled:opacity-40">← Prev</button>
            <span className="text-slate-600">Page {page} of {Math.ceil(total / 20)}</span>
            <button disabled={page >= Math.ceil(total / 20)} onClick={() => load(page + 1, q)} className="rounded border px-2 py-1 disabled:opacity-40">Next →</button>
          </div>
        )}
      </div>
    </div>
  );
}
