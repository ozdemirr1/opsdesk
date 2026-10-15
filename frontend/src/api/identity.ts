import type { UserProfile } from '../types/user';
import { requestJson } from './client';
import type { ApiResult } from './client';

export type RegisterInput = {
  email: string;
  password: string;
};

export type RegisterResult =
  | { ok: true; status: 201; data: UserProfile }
  | Extract<ApiResult, { ok: false }>;

/**
 * Checks whether a value is a non-null, non-array object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Validates whether an unknown value conforms to the UserProfile contract.
 */
export function isUserProfile(value: unknown): value is UserProfile {
  if (!isRecord(value)) {
    return false;
  }

  const { user_id, email, is_active } = value;

  // Validate user_id: must be a positive safe integer
  if (
    typeof user_id !== 'number' ||
    !Number.isSafeInteger(user_id) ||
    user_id <= 0
  ) {
    return false;
  }

  // Validate email: must be a non-empty string
  if (typeof email !== 'string' || email.length === 0) {
    return false;
  }

  // Validate is_active: must be a boolean (false is valid)
  if (typeof is_active !== 'boolean') {
    return false;
  }

  return true;
}

/**
 * Sends a registration request to create a new user account.
 */
export async function registerUser(
  input: RegisterInput,
  signal?: AbortSignal
): Promise<RegisterResult> {
  // Explicitly pick only email and password to prevent leaking extraneous fields
  const body = JSON.stringify({
    email: input.email,
    password: input.password,
  });

  const result = await requestJson('/users', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body,
    signal,
  });

  // Preserve any underlying request errors (network, http, aborted, invalid_response)
  if (!result.ok) {
    return result;
  }

  // Contract requirement: Must return HTTP 201 and a valid UserProfile payload
  if (result.status === 201 && isUserProfile(result.data)) {
    return {
      ok: true,
      status: 201,
      data: result.data,
    };
  }

  return {
    ok: false,
    kind: 'invalid_response',
    status: result.status,
    message: 'The server returned an unexpected response.',
  };
}
