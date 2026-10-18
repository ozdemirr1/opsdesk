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

export type AccessTokenResponse = {
  access_token: string;
  token_type: 'bearer';
};

export type LoginInput = {
  email: string;
  password: string;
};

export type LoginResult =
  | { ok: true; status: 200; data: AccessTokenResponse }
  | Extract<ApiResult, { ok: false }>;

export type CurrentUserResult =
  | { ok: true; status: 200; data: UserProfile }
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
 * Validates whether an unknown value conforms to the AccessTokenResponse contract.
 */
export function isAccessTokenResponse(
  value: unknown
): value is AccessTokenResponse {
  if (!isRecord(value)) {
    return false;
  }

  const { access_token, token_type } = value;

  // Validate access_token: must be a non-empty string
  if (typeof access_token !== 'string' || access_token.length === 0) {
    return false;
  }

  // Validate token_type: must be strictly 'bearer'
  if (token_type !== 'bearer') {
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

/**
 * Sends a login request to authenticate a user and retrieve an access token.
 */
export async function loginUser(
  input: LoginInput,
  signal?: AbortSignal
): Promise<LoginResult> {
  // Explicitly pick only email and password to prevent leaking extraneous fields
  const body = JSON.stringify({
    email: input.email,
    password: input.password,
  });

  const result = await requestJson('/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body,
    signal,
  });

  if (!result.ok) {
    return result;
  }

  // Contract requirement: Must return HTTP 200 and a valid AccessTokenResponse payload
  if (result.status === 200 && isAccessTokenResponse(result.data)) {
    return {
      ok: true,
      status: 200,
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

/**
 * Fetches the currently authenticated user profile using a bearer access token.
 */
export async function getCurrentUser(
  token: string,
  signal?: AbortSignal
): Promise<CurrentUserResult> {
  const result = await requestJson('/users/me', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    signal,
  });

  if (!result.ok) {
    return result;
  }

  // Contract requirement: Must return HTTP 200 and a valid UserProfile payload
  if (result.status === 200 && isUserProfile(result.data)) {
    return {
      ok: true,
      status: 200,
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
