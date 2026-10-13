import { describe, expect, test } from 'vitest';
import { isApiErrorResponse, getApiErrorMessage } from './errors';

describe('isApiErrorResponse', () => {
  test('accepts valid error response structure', () => {
    const validPayload = {
      error: {
        code: 'email_already_exists',
        message: 'Email already exists.',
        details: [{ field: 'email', reason: 'duplicate' }],
      },
    };

    expect(isApiErrorResponse(validPayload)).toBe(true);
  });

  test('accepts valid error response with empty details', () => {
    const validPayload = {
      error: {
        code: 'unauthenticated',
        message: 'Invalid credentials',
        details: [],
      },
    };

    expect(isApiErrorResponse(validPayload)).toBe(true);
  });

  test('rejects null, primitives, and arrays', () => {
    expect(isApiErrorResponse(null)).toBe(false);
    expect(isApiErrorResponse(undefined)).toBe(false);
    expect(isApiErrorResponse('error string')).toBe(false);
    expect(isApiErrorResponse(123)).toBe(false);
    expect(isApiErrorResponse([])).toBe(false);
  });

  test('rejects objects with missing required fields', () => {
    expect(isApiErrorResponse({})).toBe(false);
    expect(isApiErrorResponse({ error: {} })).toBe(false);
    expect(
      isApiErrorResponse({
        error: {
          code: 'validation_error',
          message: 'Failed',
        },
      })
    ).toBe(false);
  });

  test('rejects numeric code or invalid details entries', () => {
    expect(
      isApiErrorResponse({
        error: {
          code: 400,
          message: 'Bad Request',
          details: [],
        },
      })
    ).toBe(false);

    expect(
      isApiErrorResponse({
        error: {
          code: 'bad_request',
          message: 'Failed',
          details: ['not an object'],
        },
      })
    ).toBe(false);

    expect(
      isApiErrorResponse({
        error: {
          code: 'bad_request',
          message: 'Failed',
          details: [{ field: 123 }],
        },
      })
    ).toBe(false);
  });
});

describe('getApiErrorMessage', () => {
  test('translates known error codes to specific frontend messages', () => {
    const createError = (code: string) => ({
      error: { code, message: 'Server message', details: [] },
    });

    expect(getApiErrorMessage(createError('email_already_exists'))).toBe(
      'An account with this email already exists.'
    );
    expect(getApiErrorMessage(createError('unauthenticated'))).toBe(
      'Authentication failed. Please sign in again.'
    );
    expect(getApiErrorMessage(createError('validation_error'))).toBe(
      'Please check the submitted fields.'
    );
  });

  test('returns fallback message for unknown error codes', () => {
    const unknownError = {
      error: { code: 'unknown_service_error', message: 'Failed', details: [] },
    };

    expect(getApiErrorMessage(unknownError)).toBe(
      'Something went wrong. Please try again.'
    );
  });

  test('returns fallback message for invalid payloads', () => {
    expect(getApiErrorMessage(null)).toBe('Something went wrong. Please try again.');
    expect(getApiErrorMessage('<html>502 Bad Gateway</html>')).toBe(
      'Something went wrong. Please try again.'
    );
  });

  test('does not leak arbitrary backend messages to user-facing output', () => {
    const sensitiveError = {
      error: {
        code: 'unauthenticated',
        message: 'Database query failed: user table deadlocked',
        details: [],
      },
    };

    const message = getApiErrorMessage(sensitiveError);
    expect(message).toBe('Authentication failed. Please sign in again.');
    expect(message).not.toContain('Database query failed');
  });
});
