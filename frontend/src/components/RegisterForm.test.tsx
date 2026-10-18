import { beforeEach, describe, expect, test, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RegisterForm from './RegisterForm';
import { registerUser } from '../api/identity';
import type { RegisterResult } from '../api/identity';

vi.mock('../api/identity', () => ({ registerUser: vi.fn() }));

const validPassword = 'validPassword123';
const successMessage = 'Account created. You are not signed in.';
const uncertainMessage =
  'Registration could not be confirmed. The account may have been created.';
const success: RegisterResult = {
  ok: true,
  status: 201,
  data: { user_id: 10, email: 'user@example.com', is_active: true },
};
const conflict: RegisterResult = {
  ok: false,
  kind: 'http',
  status: 409,
  message: 'An account with this email already exists.',
};
const networkFailure: RegisterResult = {
  ok: false,
  kind: 'network',
  status: null,
  message: 'Could not reach the server. Please try again.',
};
const invalidResponse: RegisterResult = {
  ok: false,
  kind: 'invalid_response',
  status: 201,
  message: 'The server returned an unexpected response.',
};

function fields() {
  return {
    email: screen.getByLabelText(/email/i),
    password: screen.getByLabelText(/^Password/i),
    confirmation: screen.getByLabelText(/^Confirm password/i),
  };
}

async function fillForm(
  user: ReturnType<typeof userEvent.setup>,
  email = 'user@example.com',
  password = validPassword,
  confirmation = password,
) {
  const inputs = fields();
  await user.type(inputs.email, email);
  await user.type(inputs.password, password);
  await user.type(inputs.confirmation, confirmation);
  return inputs;
}

function deferredResult() {
  let resolve!: (result: RegisterResult) => void;
  const promise = new Promise<RegisterResult>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function expectEditable() {
  for (const input of Object.values(fields())) {
    expect(input).toBeEnabled();
  }
  expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled();
}

describe('RegisterForm', () => {
  beforeEach(() => {
    vi.mocked(registerUser).mockReset();
  });

  test('allows typing in all three fields without sending a request', async () => {
    const user = userEvent.setup();
    render(<RegisterForm />);
    const inputs = await fillForm(user);
    expect(inputs.email).toHaveValue('user@example.com');
    expect(inputs.password).toHaveValue(validPassword);
    expect(inputs.confirmation).toHaveValue(validPassword);
    expect(registerUser).not.toHaveBeenCalled();
  });

  test.each([
    ['empty', '', 'Email is required.'],
    ['non-ASCII', 'kullanıcı@example.com', 'Enter a valid email address.'],
    ['over 254 characters', `${'a'.repeat(245)}@example.com`, 'Enter a valid email address.'],
    ['invalid ASCII format', 'invalid-email', 'Enter a valid email address.'],
  ])('rejects %s email without calling the API', async (_name, email, message) => {
    const user = userEvent.setup();
    render(<RegisterForm />);
    if (email) await user.type(fields().email, email);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(registerUser).not.toHaveBeenCalled();
  });

  test.each([
    ['empty', '', 'Password is required.'],
    ['14 code points', 'a'.repeat(14), 'Password must be between 15 and 128 characters.'],
    ['129 code points', 'a'.repeat(129), 'Password must be between 15 and 128 characters.'],
    ['8 astral code points (16 UTF-16 units)', '😀'.repeat(8), 'Password must be between 15 and 128 characters.'],
  ])('rejects %s password without calling the API', async (_name, password, message) => {
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.type(fields().email, 'user@example.com');
    if (password) await user.type(fields().password, password);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(registerUser).not.toHaveBeenCalled();
  });

  test.each([15, 128])('accepts a password of exactly %i code points', async (length) => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(success);
    render(<RegisterForm />);
    await fillForm(user, 'user@example.com', 'a'.repeat(length));
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(successMessage);
    expect(registerUser).toHaveBeenCalledTimes(1);
  });

  test('requires confirmation, then succeeds after correcting a mismatch and pressing Enter', async () => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(success);
    render(<RegisterForm />);
    const inputs = fields();
    await user.type(inputs.email, 'user@example.com');
    await user.type(inputs.password, validPassword);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Confirm your password.');
    expect(registerUser).not.toHaveBeenCalled();
    await user.type(inputs.confirmation, 'differentPassword123');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(registerUser).not.toHaveBeenCalled();
    await user.clear(inputs.confirmation);
    await user.type(inputs.confirmation, `${validPassword}{Enter}`);
    expect(await screen.findByRole('status')).toHaveTextContent(successMessage);
    expect(registerUser).toHaveBeenCalledTimes(1);
  });

  test('normalizes both passwords with NFC and sends only email and normalized password', async () => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(success);
    render(<RegisterForm />);
    await fillForm(user, 'user@example.com', 'Cafe\u0301Password123', 'Caf\u00e9Password123');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(successMessage);
    expect(registerUser).toHaveBeenCalledWith(
      { email: 'user@example.com', password: 'Caf\u00e9Password123' },
      expect.any(AbortSignal),
    );
  });

  test('keeps all controls disabled, prevents duplicate submits and waits for verified success', async () => {
    const user = userEvent.setup();
    const pending = deferredResult();
    vi.mocked(registerUser).mockReturnValueOnce(pending.promise);
    render(<RegisterForm />);
    const inputs = await fillForm(user);
    const button = screen.getByRole('button', { name: 'Create account' });
    await user.click(button);
    for (const input of Object.values(inputs)) expect(input).toBeDisabled();
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent('Creating account...');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    await user.click(button);
    // Exercise the handler's guard as well as the disabled button.
    const form = button.closest('form');
    if (!form) throw new Error('Submit button must belong to a form.');
    fireEvent.submit(form);
    expect(registerUser).toHaveBeenCalledTimes(1);
    await act(async () => {
      pending.resolve(success);
      await pending.promise;
    });
    expect(screen.getByRole('status')).toHaveTextContent(successMessage);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(inputs.email).toHaveValue('user@example.com');
    expect(inputs.password).toHaveValue('');
    expect(inputs.confirmation).toHaveValue('');
    expectEditable();
  });

  test('shows a safe conflict message, preserves input and allows a corrected submission', async () => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(conflict).mockResolvedValueOnce(success);
    render(<RegisterForm />);
    const inputs = await fillForm(user, 'exists@example.com');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(conflict.message);
    expectEditable();
    expect(inputs.password).toHaveValue(validPassword);
    expect(inputs.confirmation).toHaveValue(validPassword);
    await user.clear(inputs.email);
    await user.type(inputs.email, 'user@example.com');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(successMessage);
    expect(registerUser).toHaveBeenCalledTimes(2);
  });

  test.each([networkFailure, invalidResponse])('shows an uncertain outcome for $kind and unlocks controls', async (failure) => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(failure);
    render(<RegisterForm />);
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(uncertainMessage);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expectEditable();
    expect(registerUser).toHaveBeenCalledTimes(1);
  });

  test('clears the old error when retrying unchanged input while the new request is pending', async () => {
    const user = userEvent.setup();
    const pending = deferredResult();
    vi.mocked(registerUser).mockResolvedValueOnce(networkFailure).mockReturnValueOnce(pending.promise);
    render(<RegisterForm />);
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(uncertainMessage);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    try {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Creating account...' })).toBeDisabled();
      expect(registerUser).toHaveBeenCalledTimes(2);
    } finally {
      // Settle the promise even when the regression assertion fails.
      await act(async () => {
        pending.resolve(success);
        await pending.promise;
      });
    }
    expect(screen.getByRole('status')).toHaveTextContent(successMessage);
    expectEditable();
  });

  test('aborts on unmount and a late response does not alter a newly opened form', async () => {
    const user = userEvent.setup();
    const pending = deferredResult();
    vi.mocked(registerUser).mockReturnValueOnce(pending.promise);
    const { unmount } = render(<RegisterForm />);
    await fillForm(user, 'old@example.com');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    const signal = vi.mocked(registerUser).mock.calls[0][1];
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
    render(<RegisterForm />);
    const freshInputs = await fillForm(user, 'fresh@example.com', 'freshPassword123');
    await act(async () => {
      pending.resolve(success);
      await pending.promise;
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(freshInputs.email).toHaveValue('fresh@example.com');
    expect(freshInputs.password).toHaveValue('freshPassword123');
    expect(freshInputs.confirmation).toHaveValue('freshPassword123');
    expectEditable();
    expect(registerUser).toHaveBeenCalledTimes(1);
  });

  test.each(['email', 'password', 'confirmation'] as const)('clears validation feedback when %s is edited', async (field) => {
    const user = userEvent.setup();
    render(<RegisterForm />);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    await user.type(fields()[field], 'a');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(registerUser).not.toHaveBeenCalled();
  });

  test.each(['email', 'password', 'confirmation'] as const)('clears success feedback when %s is edited', async (field) => {
    const user = userEvent.setup();
    vi.mocked(registerUser).mockResolvedValueOnce(success);
    render(<RegisterForm />);
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(successMessage);
    await user.type(fields()[field], 'a');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(registerUser).toHaveBeenCalledTimes(1);
  });
});
