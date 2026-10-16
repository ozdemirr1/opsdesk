import { beforeEach, describe, expect, test, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginForm from './LoginForm';
import { loginUser, getCurrentUser } from '../api/identity';
import type { CurrentUserResult, LoginResult } from '../api/identity';

vi.mock('../api/identity', () => ({
  loginUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

describe('LoginForm', () => {
  beforeEach(() => {
    vi.mocked(loginUser).mockReset();
    vi.mocked(getCurrentUser).mockReset();
  });

  test('allows typing in fields and updates their values', async () => {
    const user = userEvent.setup();
    render(<LoginForm onAuthenticated={vi.fn()} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'validPassword123');

    expect(emailInput).toHaveValue('test@example.com');
    expect(passwordInput).toHaveValue('validPassword123');
  });

  test('validates email without calling loginUser: empty, non-ASCII, too long, invalid format', async () => {
    const user = userEvent.setup();
    render(<LoginForm onAuthenticated={vi.fn()} />);

    const emailInput = screen.getByLabelText(/email/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    // 1. Empty email
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Email is required.');
    expect(loginUser).not.toHaveBeenCalled();

    // 2. Non-ASCII email
    await user.type(emailInput, 'kullanıcı@example.com');
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(loginUser).not.toHaveBeenCalled();

    // 3. Email longer than 254 characters
    await user.clear(emailInput);
    await user.type(emailInput, `${'a'.repeat(245)}@example.com`);
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(loginUser).not.toHaveBeenCalled();

    // 4. Invalid email format
    await user.clear(emailInput);
    await user.type(emailInput, 'not-an-email');
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(loginUser).not.toHaveBeenCalled();
  });

  test('validates password requirements without calling loginUser: empty, < 15, > 128', async () => {
    const user = userEvent.setup();
    render(<LoginForm onAuthenticated={vi.fn()} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'valid@example.com');

    // 1. Empty password
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Password is required.');
    expect(loginUser).not.toHaveBeenCalled();

    // 2. Too short (< 15 characters)
    await user.type(passwordInput, 'shortPass1234');
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Password must be between 15 and 128 characters.'
    );
    expect(loginUser).not.toHaveBeenCalled();

    // 3. Too long (> 128 characters)
    await user.clear(passwordInput);
    await user.type(passwordInput, 'a'.repeat(129));
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Password must be between 15 and 128 characters.'
    );
    expect(loginUser).not.toHaveBeenCalled();
  });

  test('authenticates successfully: calls loginUser, calls getCurrentUser with token, and triggers onAuthenticated', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    vi.mocked(loginUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { access_token: 'valid-jwt-token', token_type: 'bearer' },
    });

    vi.mocked(getCurrentUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { user_id: 1, email: 'operator@example.com', is_active: true },
    });

    render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'operator@example.com');
    await user.type(passwordInput, 'validPassword123');
    await user.click(submitBtn);

    expect(loginUser).toHaveBeenCalledTimes(1);
    expect(loginUser).toHaveBeenCalledWith(
      { email: 'operator@example.com', password: 'validPassword123' },
      expect.any(AbortSignal)
    );

    await waitFor(() => {
      expect(getCurrentUser).toHaveBeenCalledTimes(1);
    });
    expect(getCurrentUser).toHaveBeenCalledWith('valid-jwt-token', expect.any(AbortSignal));

    expect(onAuthenticated).toHaveBeenCalledTimes(1);
    expect(onAuthenticated).toHaveBeenCalledWith({
      accessToken: 'valid-jwt-token',
      user: { user_id: 1, email: 'operator@example.com', is_active: true },
    });

    expect(passwordInput).toHaveValue('');
    expect(emailInput).toHaveValue('operator@example.com');
  });

  test('shows error and does not call getCurrentUser on login 401', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    vi.mocked(loginUser).mockResolvedValue({
      ok: false,
      kind: 'http',
      status: 401,
      message: 'Authentication failed. Please sign in again.',
    });

    render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'wrong@example.com');
    await user.type(passwordInput, 'wrongPassword123');
    await user.click(submitBtn);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Email or password is incorrect.');
    expect(getCurrentUser).not.toHaveBeenCalled();
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  test('does not establish session if getCurrentUser fails', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    vi.mocked(loginUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { access_token: 'valid-token', token_type: 'bearer' },
    });

    vi.mocked(getCurrentUser).mockResolvedValue({
      ok: false,
      kind: 'http',
      status: 500,
      message: 'Something went wrong. Please try again.',
    });

    render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'user@example.com');
    await user.type(passwordInput, 'validPassword123');
    await user.click(submitBtn);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Something went wrong. Please try again.');
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  test('does not establish session if user profile is inactive (is_active: false)', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    vi.mocked(loginUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { access_token: 'valid-token', token_type: 'bearer' },
    });

    vi.mocked(getCurrentUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { user_id: 2, email: 'inactive@example.com', is_active: false },
    });

    render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'inactive@example.com');
    await user.type(passwordInput, 'validPassword123');
    await user.click(submitBtn);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Account is inactive. Please contact support.');
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  test('disables inputs, updates button text to Signing in..., and prevents duplicate submissions while pending', async () => {
    const user = userEvent.setup();

    let resolveLogin!: (value: LoginResult) => void;
    const pendingPromise = new Promise<LoginResult>((resolve) => {
      resolveLogin = resolve;
    });
    vi.mocked(loginUser).mockReturnValue(pendingPromise);

    render(<LoginForm onAuthenticated={vi.fn()} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'pending@example.com');
    await user.type(passwordInput, 'validPassword123');
    await user.click(submitBtn);

    expect(emailInput).toBeDisabled();
    expect(passwordInput).toBeDisabled();
    expect(submitBtn).toBeDisabled();
    expect(submitBtn).toHaveTextContent('Signing in...');
    expect(loginUser).toHaveBeenCalledTimes(1);

    // A direct submit also exercises the immediate request guard.
    await user.click(submitBtn);
    fireEvent.submit(submitBtn.closest('form')!);
    expect(loginUser).toHaveBeenCalledTimes(1);

    // Prepare profile resolution and complete login
    vi.mocked(getCurrentUser).mockResolvedValue({
      ok: true,
      status: 200,
      data: { user_id: 1, email: 'pending@example.com', is_active: true },
    });

    await act(async () => {
      resolveLogin({
        ok: true,
        status: 200,
        data: { access_token: 'tok-1', token_type: 'bearer' },
      });
      await pendingPromise;
    });

    await waitFor(() => {
      expect(submitBtn).toHaveTextContent('Sign in');
    });
    expect(emailInput).not.toBeDisabled();
  });

  test('aborts pending request on unmount and ignores delayed response', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    let capturedSignal!: AbortSignal;
    let resolveLogin!: (value: LoginResult) => void;

    vi.mocked(loginUser).mockImplementation((_input, signal) => {
      capturedSignal = signal!;
      return new Promise<LoginResult>((resolve) => {
        resolveLogin = resolve;
      });
    });

    const { unmount } = render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'unmount@example.com');
    await user.type(passwordInput, 'validPassword123');
    await user.click(submitBtn);

    expect(capturedSignal.aborted).toBe(false);

    unmount();

    expect(capturedSignal.aborted).toBe(true);

    await act(async () => {
      resolveLogin({
        ok: true,
        status: 200,
        data: { access_token: 'tok', token_type: 'bearer' },
      });
    });

    expect(getCurrentUser).not.toHaveBeenCalled();
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  test('allows resubmitting with Enter key after correcting an error', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    vi.mocked(loginUser).mockResolvedValueOnce({
      ok: false,
      kind: 'http',
      status: 401,
      message: 'Authentication failed. Please sign in again.',
    });

    render(<LoginForm onAuthenticated={onAuthenticated} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    await user.type(emailInput, 'user@example.com');
    await user.type(passwordInput, 'wrongPassword123');
    await user.click(submitBtn);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Email or password is incorrect.');
    expect(onAuthenticated).not.toHaveBeenCalled();

    // Prepare successful responses
    vi.mocked(loginUser).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: { access_token: 'new-token', token_type: 'bearer' },
    });
    vi.mocked(getCurrentUser).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: { user_id: 1, email: 'user@example.com', is_active: true },
    });

    await user.clear(passwordInput);
    await user.type(passwordInput, 'correctPassword1{Enter}');

    await waitFor(() => {
      expect(onAuthenticated).toHaveBeenCalledTimes(1);
    });
    expect(onAuthenticated).toHaveBeenCalledWith({
      accessToken: 'new-token',
      user: { user_id: 1, email: 'user@example.com', is_active: true },
    });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('clears error message when email or password is edited', async () => {
    const user = userEvent.setup();
    render(<LoginForm onAuthenticated={vi.fn()} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: 'Sign in' });

    // Trigger empty email error
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Email is required.');

    // Type in email to clear error
    await user.type(emailInput, 'a');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    // Trigger empty password error
    await user.clear(emailInput);
    await user.type(emailInput, 'valid@example.com');
    await user.click(submitBtn);
    expect(screen.getByRole('alert')).toHaveTextContent('Password is required.');

    // Type in password to clear error
    await user.type(passwordInput, 'p');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('clears previous error while retrying unchanged credentials', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();
    let resolveRetry!: (value: LoginResult) => void;
    const pendingRetry = new Promise<LoginResult>((resolve) => {
      resolveRetry = resolve;
    });
    vi.mocked(loginUser)
      .mockResolvedValueOnce({
        ok: false, kind: 'network', status: null,
        message: 'Could not reach the server. Please try again.',
      })
      .mockReturnValueOnce(pendingRetry);
    render(<LoginForm onAuthenticated={onAuthenticated} />);
    await user.type(screen.getByLabelText(/email/i), 'retry@example.com');
    await user.type(screen.getByLabelText(/password/i), 'syntheticPassword1');
    const button = screen.getByRole('button', { name: 'Sign in' });
    await user.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server.');

    await user.click(button);
    expect(loginUser).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(button).toHaveTextContent('Signing in...');
    expect(button).toBeDisabled();
    expect(onAuthenticated).not.toHaveBeenCalled();

    await act(async () => {
      resolveRetry({
        ok: false, kind: 'http', status: 401,
        message: 'Authentication failed. Please sign in again.',
      });
      await pendingRetry;
    });
    expect(button).toBeEnabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Email or password is incorrect.');
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  test.each(['login', 'profile'] as const)(
    'silently handles an aborted %s result and permits another attempt',
    async (stage) => {
      const user = userEvent.setup();
      const onAuthenticated = vi.fn();
      const cancelled = {
        ok: false, kind: 'aborted', status: null, message: 'Request cancelled.',
      } as const;
      const tokenReply = {
        ok: true, status: 200,
        data: { access_token: 'synthetic-token', token_type: 'bearer' },
      } as const;
      if (stage === 'login') {
        vi.mocked(loginUser).mockResolvedValueOnce(cancelled);
      } else {
        vi.mocked(loginUser).mockResolvedValueOnce(tokenReply);
        vi.mocked(getCurrentUser).mockResolvedValueOnce(cancelled);
      }
      render(<LoginForm onAuthenticated={onAuthenticated} />);
      const email = screen.getByLabelText(/email/i);
      const password = screen.getByLabelText(/password/i);
      const button = screen.getByRole('button', { name: 'Sign in' });
      await user.type(email, 'cancel@example.com');
      await user.type(password, 'syntheticPassword1');
      await user.click(button);

      await waitFor(() => expect(button).toBeEnabled());
      expect(email).toBeEnabled();
      expect(password).toBeEnabled();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(onAuthenticated).not.toHaveBeenCalled();
      expect(getCurrentUser).toHaveBeenCalledTimes(stage === 'login' ? 0 : 1);

      vi.mocked(loginUser).mockResolvedValueOnce(tokenReply);
      vi.mocked(getCurrentUser).mockResolvedValueOnce({
        ok: true, status: 200,
        data: { user_id: 1, email: 'cancel@example.com', is_active: true },
      });
      await user.clear(password);
      await user.type(password, 'syntheticPassword1{Enter}');
      await waitFor(() => expect(onAuthenticated).toHaveBeenCalledTimes(1));
      expect(loginUser).toHaveBeenCalledTimes(2);
    }
  );

  test('keeps controls disabled until the profile resolves using the same signal', async () => {
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();
    let resolveProfile!: (value: CurrentUserResult) => void;
    const pendingProfile = new Promise<CurrentUserResult>((resolve) => {
      resolveProfile = resolve;
    });
    vi.mocked(loginUser).mockResolvedValueOnce({
      ok: true, status: 200,
      data: { access_token: 'synthetic-token', token_type: 'bearer' },
    });
    vi.mocked(getCurrentUser).mockReturnValueOnce(pendingProfile);
    render(<LoginForm onAuthenticated={onAuthenticated} />);
    const email = screen.getByLabelText(/email/i);
    const password = screen.getByLabelText(/password/i);
    const button = screen.getByRole('button', { name: 'Sign in' });
    await user.type(email, 'profile@example.com');
    await user.type(password, 'syntheticPassword1');
    await user.click(button);
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalledTimes(1));

    const loginSignal = vi.mocked(loginUser).mock.calls[0][1];
    expect(loginSignal).toBeInstanceOf(AbortSignal);
    expect(getCurrentUser).toHaveBeenCalledWith('synthetic-token', loginSignal);
    expect(email).toBeDisabled();
    expect(password).toBeDisabled();
    expect(password).toHaveValue('');
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent('Signing in...');
    expect(onAuthenticated).not.toHaveBeenCalled();
    fireEvent.submit(button.closest('form')!);
    expect(loginUser).toHaveBeenCalledTimes(1);
    expect(getCurrentUser).toHaveBeenCalledTimes(1);

    const profile = { user_id: 1, email: 'profile@example.com', is_active: true };
    await act(async () => {
      resolveProfile({ ok: true, status: 200, data: profile });
      await pendingProfile;
    });
    expect(onAuthenticated).toHaveBeenCalledExactlyOnceWith({
      accessToken: 'synthetic-token', user: profile,
    });
    expect(button).toBeEnabled();
  });

  test('ignores a late profile after unmount and leaves a fresh form unauthenticated', async () => {
    const user = userEvent.setup();
    const oldAuthenticated = vi.fn();
    const freshAuthenticated = vi.fn();
    let resolveProfile!: (value: CurrentUserResult) => void;
    const pendingProfile = new Promise<CurrentUserResult>((resolve) => {
      resolveProfile = resolve;
    });
    vi.mocked(loginUser).mockResolvedValueOnce({
      ok: true, status: 200,
      data: { access_token: 'synthetic-token', token_type: 'bearer' },
    });
    vi.mocked(getCurrentUser).mockReturnValueOnce(pendingProfile);
    const { unmount } = render(<LoginForm onAuthenticated={oldAuthenticated} />);
    await user.type(screen.getByLabelText(/email/i), 'late@example.com');
    await user.type(screen.getByLabelText(/password/i), 'syntheticPassword1');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalledTimes(1));
    const signal = vi.mocked(getCurrentUser).mock.calls[0][1];
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
    render(<LoginForm onAuthenticated={freshAuthenticated} />);

    await act(async () => {
      resolveProfile({
        ok: true, status: 200,
        data: { user_id: 1, email: 'late@example.com', is_active: true },
      });
      await pendingProfile;
    });
    expect(oldAuthenticated).not.toHaveBeenCalled();
    expect(freshAuthenticated).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/email/i)).toHaveValue('');
    expect(screen.getByLabelText(/password/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
