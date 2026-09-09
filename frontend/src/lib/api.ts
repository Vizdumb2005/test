/* Typed API client. Base URL comes from VITE_API_BASE_URL (empty = same origin). */

const BASE: string = (import.meta as any).env?.VITE_API_BASE_URL ?? '';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const requestId = res.headers.get('x-request-id');
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, res.status, requestId);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  status: number;
  requestId: string | null;
  constructor(message: string, status: number, requestId: string | null) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

export const apiBase = BASE;

/* ---- Response shapes (subset of backend schemas) ---- */
export interface RetrievalItem {
  rank: number;
  score: number;
  retrieval_method: string;
  document_id: string;
  chunk_id: string;
  text: string;
  metadata: Record<string, any>;
}

export interface QueryResponse {
  query: string;
  answer: string;
  citations: Array<Record<string, any>>;
  confidence: number;
  latency_ms: Record<string, number>;
  retrieval_results: RetrievalItem[];
  request_id?: string | null;
}

export interface SearchResponse {
  query: string;
  results: RetrievalItem[];
  latency_ms: Record<string, number>;
  expanded_queries: string[];
  request_id?: string | null;
}

export interface DebugResponse {
  query: string;
  expanded_queries: string[];
  dense_results: Array<Record<string, any>>;
  sparse_results: Array<Record<string, any>>;
  fusion_results: Array<Record<string, any>>;
  reranked_results: Array<Record<string, any>>;
  final_context: Array<Record<string, any>>;
  latency_ms: Record<string, number>;
  request_id?: string | null;
}

export interface ServiceStatus {
  name: string;
  status: 'operational' | 'degraded' | 'unavailable';
  [k: string]: any;
}

export function friendlyServiceError(service: string, err: string): string {
  if (/connection refused|failed to connect|qdrant/i.test(err) && service === 'qdrant') {
    return 'Qdrant is unreachable. Start it with `docker compose up -d qdrant`, then retry.';
  }
  return err;
}
