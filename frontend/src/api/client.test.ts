import { afterEach, describe, expect, test, vi } from 'vitest';
import { requestJson } from './client';

describe('requestJson', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('constructs URL correctly and passes options to fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const options: RequestInit = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.com' }),
    };

    await requestJson('/users', options);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/users', options);
  });

  test('returns ok: true with status and parsed data on successful HTTP and valid JSON', async () => {
    const payload = { id: 101, title: 'Test Ticket' };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/tickets/101');

    expect(result).toEqual({
      ok: true,
      status: 200,
      data: payload,
    });
  });

  test('returns kind: "http" with status and mapped message on failed HTTP with valid error payload', async () => {
    const errorPayload = {
      error: {
        code: 'unauthenticated',
        message: 'Invalid credentials',
        details: [],
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/auth/login');

    expect(result).toEqual({
      ok: false,
      kind: 'http',
      status: 401,
      message: 'Authentication failed. Please sign in again.',
    });
  });

  test('returns kind: "http" with status and fallback message on failed HTTP with non-JSON body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('<html>502 Bad Gateway</html>', {
        status: 502,
        headers: { 'Content-Type': 'text/html' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/health');

    expect(result).toEqual({
      ok: false,
      kind: 'http',
      status: 502,
      message: 'Something went wrong. Please try again.',
    });
  });

  test('returns kind: "invalid_response" when HTTP is successful but JSON cannot be parsed', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('not-valid-json', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/data');

    expect(result).toEqual({
      ok: false,
      kind: 'invalid_response',
      status: 200,
      message: 'The server returned an unexpected response.',
    });
  });

  test('returns kind: "network" with status: null when fetch rejects due to network failure', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/users');

    expect(result).toEqual({
      ok: false,
      kind: 'network',
      status: null,
      message: 'Could not reach the server. Please try again.',
    });
  });

  test('returns kind: "aborted" with status: null when request is aborted', async () => {
    const abortError = new DOMException('The user aborted a request.', 'AbortError');
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal('fetch', fetchMock);

    const result = await requestJson('/users');

    expect(result).toEqual({
      ok: false,
      kind: 'aborted',
      status: null,
      message: 'Request cancelled.',
    });
  });


test('returns kind: "aborted" when reading response body is aborted on HTTP 200', async () => {
    const response = new Response('{}', { status: 200 });
    vi.spyOn(response, 'json').mockRejectedValue(
      new DOMException('Request cancelled.', 'AbortError')
    );
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));

    const result = await requestJson('/data');

    expect(result).toEqual({
      ok: false,
      kind: 'aborted',
      status: null,
      message: 'Request cancelled.',
    });
  });

  test('returns kind: "aborted" when reading error body is aborted on HTTP 401', async () => {
    const response = new Response('{}', { status: 401 });
    vi.spyOn(response, 'json').mockRejectedValue(
      new DOMException('Request cancelled.', 'AbortError')
    );
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));

    const result = await requestJson('/auth/login');

    expect(result).toEqual({
      ok: false,
      kind: 'aborted',
      status: null,
      message: 'Request cancelled.',
    });
  });
});
