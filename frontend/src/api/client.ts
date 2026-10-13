import { API_BASE_URL } from './config';
import { getApiErrorMessage } from './errors';

export type ApiResult =
  | { ok: true; status: number; data: unknown }
  | {
      ok: false;
      kind: 'http' | 'network' | 'invalid_response' | 'aborted';
      status: number | null;
      message: string;
    };

/**
 * Checks whether an error is an AbortError.
 */
function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    error.name === 'AbortError'
  );
}

/**
 * Combines base URL and relative path ensuring exactly one separating slash.
 */
function buildUrl(base: string, path: string): string {
  const normalizedBase = base.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');
  return normalizedPath ? `${normalizedBase}/${normalizedPath}` : normalizedBase;
}

/**
 * Sends an HTTP request expecting a JSON response and returns a discriminated union result.
 */
export async function requestJson(
  path: string,
  options: RequestInit = {}
): Promise<ApiResult> {
  const url = buildUrl(API_BASE_URL, path);

  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (isAbortError(error)) {
      return {
        ok: false,
        kind: 'aborted',
        status: null,
        message: 'Request cancelled.',
      };
    }

    return {
      ok: false,
      kind: 'network',
      status: null,
      message: 'Could not reach the server. Please try again.',
    };
  }

  // Handle successful HTTP status codes (200-299)
  if (response.ok) {
    try {
      const data: unknown = await response.json();
      return {
        ok: true,
        status: response.status,
        data,
      };
    } catch (error) {
      if (isAbortError(error)) {
        return {
          ok: false,
          kind: 'aborted',
          status: null,
          message: 'Request cancelled.',
        };
      }

      return {
        ok: false,
        kind: 'invalid_response',
        status: response.status,
        message: 'The server returned an unexpected response.',
      };
    }
  }

  // Handle failed HTTP status codes (4xx, 5xx)
  let errorData: unknown;
  try {
    errorData = await response.json();
  } catch (error) {
    if (isAbortError(error)) {
      return {
        ok: false,
        kind: 'aborted',
        status: null,
        message: 'Request cancelled.',
      };
    }
    errorData = null;
  }

  return {
    ok: false,
    kind: 'http',
    status: response.status,
    message: getApiErrorMessage(errorData),
  };
}
