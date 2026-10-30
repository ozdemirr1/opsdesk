import { requestJson, type ApiResult } from './client';

export type ResourceResult<T> =
  | { ok: true; status: number; data: T }
  | Extract<ApiResult, { ok: false }>
  | { ok: false; kind: 'invalid_request'; status: null; message: string };

export type Page<T> = { items: T[]; total_count: number; limit: number; offset: number };
export type PageQuery = { limit?: number; offset?: number };
export type Guard<T> = (value: unknown) => value is T;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isSafeCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

export function isId(value: unknown): value is number {
  return isSafeCount(value) && value > 0;
}

export function isPage<T>(value: unknown, guard: Guard<T>): value is Page<T> {
  if (!isRecord(value) || !Array.isArray(value.items) ||
      !isSafeCount(value.total_count) || !isId(value.limit) || value.limit > 100 ||
      !isSafeCount(value.offset) || !value.items.every(guard)) return false;
  return value.items.length === Math.min(value.limit, Math.max(0, value.total_count - value.offset));
}

export function matchesPage<T>(page: Page<T>, query: PageQuery): boolean {
  return page.limit === (query.limit ?? 20) && page.offset === (query.offset ?? 0);
}

export function validPageQuery(query: PageQuery): boolean {
  return (query.limit === undefined || (isId(query.limit) && query.limit <= 100)) &&
    (query.offset === undefined || isSafeCount(query.offset));
}

export function pageParams(query: PageQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.limit !== undefined) params.set('limit', String(query.limit));
  if (query.offset !== undefined) params.set('offset', String(query.offset));
  return params;
}

export function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function invalidRequest(): Extract<ResourceResult<never>, { kind: 'invalid_request' }> {
  return { ok: false, kind: 'invalid_request', status: null, message: 'Invalid request parameters.' };
}

/** Resource adapters share transport but do not own session or screen state. */
export async function requestResource<T>(
  path: string, token: string, guard: Guard<T>,
  options: { signal?: AbortSignal; body?: { name: string } | { content: string }; expectedStatus?: number } = {},
): Promise<ResourceResult<T>> {
  if (typeof token !== 'string' || !token.trim() || /[\r\n]/u.test(token)) return invalidRequest();
  const cancelled = () => ({ ok: false, kind: 'aborted', status: null, message: 'Request cancelled.' } as const);
  if (options.signal?.aborted) return cancelled();
  const result = await requestJson(path, {
    method: options.body ? 'POST' : 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    signal: options.signal,
  });
  // Some fetch implementations finish even after cancellation.
  if (options.signal?.aborted) return cancelled();
  if (!result.ok) return result;
  if (result.status !== (options.expectedStatus ?? 200) || !guard(result.data)) {
    return { ok: false, kind: 'invalid_response', status: result.status,
      message: 'The server returned an unexpected response.' };
  }
  return { ok: true, status: result.status, data: result.data };
}
