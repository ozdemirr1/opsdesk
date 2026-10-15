import { afterEach, describe, expect, test, vi } from 'vitest';
import { isUserProfile, registerUser } from './identity';

describe('isUserProfile', () => {
  test('accepts valid user profile', () => {
    const validProfile = {
      user_id: 1,
      email: 'user@example.com',
      is_active: true,
    };

    expect(isUserProfile(validProfile)).toBe(true);
  });

  test('accepts profile with is_active as false', () => {
    const inactiveProfile = {
      user_id: 42,
      email: 'inactive@example.com',
      is_active: false,
    };

    expect(isUserProfile(inactiveProfile)).toBe(true);
  });

  test('rejects null, primitives, and arrays', () => {
    expect(isUserProfile(null)).toBe(false);
    expect(isUserProfile(undefined)).toBe(false);
    expect(isUserProfile(123)).toBe(false);
    expect(isUserProfile('profile')).toBe(false);
    expect(isUserProfile([])).toBe(false);
  });

  test('rejects missing or wrongly typed fields', () => {
    expect(isUserProfile({ email: 'user@example.com', is_active: true })).toBe(false);
    expect(isUserProfile({ user_id: '1', email: 'user@example.com', is_active: true })).toBe(false);
    expect(isUserProfile({ user_id: 1, email: '', is_active: true })).toBe(false);
    expect(isUserProfile({ user_id: 1, email: 'user@example.com', is_active: 'true' })).toBe(false);
  });

  test('rejects zero, negative, float, or unsafe integers for user_id', () => {
    expect(isUserProfile({ user_id: 0, email: 'user@example.com', is_active: true })).toBe(false);
    expect(isUserProfile({ user_id: -10, email: 'user@example.com', is_active: true })).toBe(false);
    expect(isUserProfile({ user_id: 1.5, email: 'user@example.com', is_active: true })).toBe(false);
    expect(
      isUserProfile({
        user_id: Number.MAX_SAFE_INTEGER + 1,
        email: 'user@example.com',
        is_active: true,
      })
    ).toBe(false);
  });
});

describe('registerUser', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('returns successful profile on valid 201 response', async () => {
    const mockProfile = {
      user_id: 10,
      email: 'newuser@example.com',
      is_active: true,
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockProfile), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await registerUser({
      email: 'newuser@example.com',
      password: 'validPassword123',
    });

    expect(result).toEqual({
      ok: true,
      status: 201,
      data: mockProfile,
    });
  });

  test('sends request with correct URL, method, headers, and body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user_id: 1, email: 'test@example.com', is_active: true }),
        { status: 201, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    await registerUser({
      email: 'test@example.com',
      password: 'passwordABC',
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'passwordABC',
      }),
      signal: undefined,
    });
  });

test('excludes extraneous fields such as confirmPassword from request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user_id: 1, email: 'clean@example.com', is_active: true }),
        { status: 201, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const inputWithExtra = {
      email: 'clean@example.com',
      password: 'password123',
      confirmPassword: 'password123',
    };

    await registerUser(inputWithExtra);

    const callOptions = fetchMock.mock.calls[0][1] as RequestInit;
    const parsedBody = JSON.parse(callOptions.body as string);

    expect(parsedBody).toEqual({
      email: 'clean@example.com',
      password: 'password123',
    });
    expect(parsedBody).not.toHaveProperty('confirmPassword');
  });

  test('returns invalid_response when 201 has corrupted or missing profile fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user_id: 'not-a-number' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await registerUser({
      email: 'test@example.com',
      password: 'password123',
    });

    expect(result).toEqual({
      ok: false,
      kind: 'invalid_response',
      status: 201,
      message: 'The server returned an unexpected response.',
    });
  });

  test('does not treat HTTP 200 with valid profile as registration success', async () => {
    const validProfile = {
      user_id: 1,
      email: 'user@example.com',
      is_active: true,
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(validProfile), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await registerUser({
      email: 'user@example.com',
      password: 'password123',
    });

    expect(result).toEqual({
      ok: false,
      kind: 'invalid_response',
      status: 200,
      message: 'The server returned an unexpected response.',
    });
  });

  test('preserves HTTP 409 conflict error from requestJson', async () => {
    const errorPayload = {
      error: {
        code: 'email_already_exists',
        message: 'Email already exists.',
        details: [],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await registerUser({
      email: 'exists@example.com',
      password: 'password123',
    });

    expect(result).toEqual({
      ok: false,
      kind: 'http',
      status: 409,
      message: 'An account with this email already exists.',
    });
  });

  test('preserves network error and aborted status from requestJson', async () => {
    // 1. Network failure
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const netResult = await registerUser({
      email: 'net@example.com',
      password: 'password123',
    });
    expect(netResult).toEqual({
      ok: false,
      kind: 'network',
      status: null,
      message: 'Could not reach the server. Please try again.',
    });

    // 2. Aborted request
    const abortError = new DOMException('Request cancelled.', 'AbortError');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError));
    const abortResult = await registerUser({
      email: 'abort@example.com',
      password: 'password123',
    });
    expect(abortResult).toEqual({
      ok: false,
      kind: 'aborted',
      status: null,
      message: 'Request cancelled.',
    });
  });

  test('forwards AbortSignal to fetch options', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user_id: 1, email: 'sig@example.com', is_active: true }),
        { status: 201, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const controller = new AbortController();
    await registerUser(
      { email: 'sig@example.com', password: 'password123' },
      controller.signal
    );

    const callOptions = fetchMock.mock.calls[0][1] as RequestInit;
    expect(callOptions.signal).toBe(controller.signal);
  });
});
