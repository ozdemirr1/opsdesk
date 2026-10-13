export type ApiErrorResponse = {
  error: {
    code: string;
    message: string;
    details: Record<string, string>[];
  };
};

/**
 * Checks whether a value is a non-null, non-array object.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Type guard to validate whether an unknown value matches the ApiErrorResponse schema.
 */
export function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!isRecord(value) || !('error' in value)) {
    return false;
  }

  const error = value.error;
  if (!isRecord(error)) {
    return false;
  }

  if (typeof error.code !== 'string' || typeof error.message !== 'string') {
    return false;
  }

  if (!Array.isArray(error.details)) {
    return false;
  }

  for (const item of error.details) {
    if (!isRecord(item)) {
      return false;
    }
    const values = Object.values(item);
    if (!values.every((v) => typeof v === 'string')) {
      return false;
    }
  }

  return true;
}

/**
 * Maps an API error code to a user-facing frontend message.
 */
export function getApiErrorMessage(value: unknown): string {
  if (!isApiErrorResponse(value)) {
    return 'Something went wrong. Please try again.';
  }

  switch (value.error.code) {
    case 'email_already_exists':
      return 'An account with this email already exists.';
    case 'unauthenticated':
      return 'Authentication failed. Please sign in again.';
    case 'validation_error':
      return 'Please check the submitted fields.';
    default:
      return 'Something went wrong. Please try again.';
  }
}
