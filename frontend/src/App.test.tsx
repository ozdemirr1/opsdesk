import { beforeEach, expect, test, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { navigate } from './navigation';
import { registerUser, loginUser, getCurrentUser, type CurrentUserResult } from './api/identity';

vi.mock('./api/identity', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/identity')>();
  return {
    ...actual,
    registerUser: vi.fn(),
    loginUser: vi.fn(),
    getCurrentUser: vi.fn(),
  };
});

vi.mock('./api/organizations', () => ({
  listOrganizations: vi.fn(async () => ({ ok: true, status: 200,
    data: { items: [], total_count: 0, limit: 20, offset: 0 } })),
}));

// Session controls live on Account after the directory landing.
async function openSessionScreen(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('heading', { name: 'Workspaces' });
  await user.click(screen.getByRole('button', { name: 'Account' }));
}

beforeEach(() => {
  vi.mocked(registerUser).mockReset();
  vi.mocked(loginUser).mockReset();
  vi.mocked(getCurrentUser).mockReset();
});

test.each(['/', '/login', '/organizations', '/organizations/10/tickets', '/organizations/10/tickets/1'])(
  'shows login without sample or private tickets at %s when signed out', path => {
    window.history.replaceState(null, '', `#${path}`);
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByText('Cannot access workspace')).not.toBeInTheDocument();
    for (const name of ['Tickets', 'Workspaces', 'Account', 'Sign out', 'Check session']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
  },
);

test('clears registration drafts and validation on leaving the form', async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Register' }));
  await user.type(screen.getByLabelText(/^Email/i), 'draft@example.com');
  await user.type(screen.getByLabelText(/^Password/i), 'draft-password-123');
  await user.type(screen.getByLabelText(/^Confirm password/i), 'another-password-123');
  await user.click(screen.getByRole('button', { name: 'Create account' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.click(screen.getByRole('button', { name: 'Register' }));
  expect(screen.getByLabelText(/^Email/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Password/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Confirm password/i)).toHaveValue('');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('successful registration offers login without silently creating a session', async () => {
  vi.mocked(registerUser).mockResolvedValue({ ok: true, status: 201,
    data: { user_id: 5, email: 'demo@example.com', is_active: true } });
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Register' }));
  await user.type(screen.getByLabelText(/^Email/i), 'demo@example.com');
  await user.type(screen.getByLabelText(/^Password/i), 'demo-password-123');
  await user.type(screen.getByLabelText(/^Confirm password/i), 'demo-password-123');
  await user.click(screen.getByRole('button', { name: 'Create account' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Account created. You are not signed in.');
  expect(screen.getByLabelText(/^Password/i)).toHaveValue('');
  expect(screen.queryByRole('button', { name: 'Workspaces' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('link', { name: 'Continue to login' }));
  expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(loginUser).not.toHaveBeenCalled();
});

test('authenticated root opens Workspaces, auth navigation disappears, and logout guards history', async () => {
  vi.mocked(loginUser).mockResolvedValue({ ok: true, status: 200,
    data: { access_token: 'synthetic-session', token_type: 'bearer' } });
  vi.mocked(getCurrentUser).mockResolvedValue({ ok: true, status: 200,
    data: { user_id: 1, email: 'demo@example.com', is_active: true } });
  const user = userEvent.setup();
  const view = render(<App />);
  await user.type(screen.getByLabelText(/^Email/i), 'demo@example.com');
  await user.type(screen.getByLabelText(/^Password/i), 'demo-password-123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await screen.findByRole('heading', { name: 'Workspaces' });
  expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Login' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Account' }));
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as demo@example.com');
  await act(async () => navigate('/'));
  expect(await screen.findByRole('heading', { name: 'Workspaces' })).toBeInTheDocument();
  await act(async () => navigate('/register'));
  expect(screen.queryByRole('button', { name: 'Create account' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Sign out' }));
  await act(async () => navigate('/'));
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  view.unmount();
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
});

test('handles successful session check: updates user info and keeps session active', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');
  const checkBtn = screen.getByRole('button', { name: 'Check session' });
  expect(checkBtn).toBeInTheDocument();

  // Mock updated profile for check session
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'updated-operator@example.com', is_active: true },
  });

  await user.click(checkBtn);

  expect(getCurrentUser).toHaveBeenCalledWith('test-token-123', expect.any(AbortSignal));
  expect(await screen.findByRole('status')).toHaveTextContent('Signed in as updated-operator@example.com');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
});

test('handles 401 response on check session: clears session, switches to login screen, and shows error message', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Workspaces' }));

  // Return 401 on check call
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'http',
    status: 401,
    message: 'Unauthorized',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Login' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('alert')).toHaveTextContent('Your session is no longer valid. Please sign in again.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check session' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toHaveValue('');
  expect(screen.getByLabelText(/password/i)).toHaveValue('');
});

test('clears session when user profile becomes inactive during check', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  // Return inactive user
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: false },
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Your session is no longer valid. Please sign in again.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
});

test('preserves session on network error during check and shows safe error message', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Workspaces' }));

  // Return network failure
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'network',
    status: null,
    message: 'Network request failed',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Workspaces', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Account still displays the verified session.
  await user.click(screen.getByRole('button', { name: 'Account' }));
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as operator@example.com');
});

test('preserves session on HTTP 500 server error during check and shows safe error message', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Workspaces' }));

  // Return 500 error
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'http',
    status: 500,
    message: 'Internal Server Error',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Workspaces', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Account still displays the verified session.
  await user.click(screen.getByRole('button', { name: 'Account' }));
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as operator@example.com');
});

test('preserves session on invalid response during check and shows safe error message', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Workspaces' }));

  // Return invalid response
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'invalid_response',
    status: 200,
    message: 'Invalid response format',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Workspaces', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Account still displays the verified session.
  await user.click(screen.getByRole('button', { name: 'Account' }));
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as operator@example.com');
});

test('does not show error message or alter session when check session response is aborted', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  // Return aborted result
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'aborted',
    status: null,
    message: 'Request was aborted',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  // Neither error alert nor session reset should happen
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as operator@example.com');
  expect(screen.getByRole('button', { name: 'Check session' })).toBeEnabled();
});

test('allows sign out while check session is pending and aborts in-flight request', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  let capturedSignal: AbortSignal | undefined;
  const pendingCheck = new Promise<CurrentUserResult>(() => {});
  vi.mocked(getCurrentUser).mockImplementationOnce((_token, signal) => {
    capturedSignal = signal;
    return pendingCheck;
  });

  const checkBtn = screen.getByRole('button', { name: 'Check session' });
  const signOutBtn = screen.getByRole('button', { name: 'Sign out' });

  await user.click(checkBtn);

  // Check button should be disabled during check, while Sign out remains enabled
  expect(checkBtn).toBeDisabled();
  expect(signOutBtn).toBeEnabled();
  expect(capturedSignal?.aborted).toBe(false);

  // User signs out while check is pending: signal must be aborted
  await user.click(signOutBtn);

  expect(capturedSignal?.aborted).toBe(true);
  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check session' })).not.toBeInTheDocument();
});

test('aborts pending session check when App is unmounted', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  const { unmount } = render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  let capturedSignal: AbortSignal | undefined;
  const pendingCheck = new Promise<CurrentUserResult>(() => {});
  vi.mocked(getCurrentUser).mockImplementationOnce((_token, signal) => {
    capturedSignal = signal;
    return pendingCheck;
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(capturedSignal).toBeDefined();
  expect(capturedSignal?.aborted).toBe(false);

  // Unmounting should abort the active signal
  unmount();

  expect(capturedSignal?.aborted).toBe(true);
});

test('ignores delayed 200 response arriving after sign out so session is not restored', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  let resolveCheck!: (value: CurrentUserResult) => void;
  const delayedCheckPromise = new Promise<CurrentUserResult>((resolve) => {
    resolveCheck = resolve;
  });
  vi.mocked(getCurrentUser).mockReturnValueOnce(delayedCheckPromise);

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  // Sign out while check is in-flight
  await user.click(screen.getByRole('button', { name: 'Sign out' }));

  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

  // Resolve delayed 200 OK response
  await act(async () => {
    resolveCheck({
      ok: true,
      status: 200,
      data: { user_id: 1, email: 'operator@example.com', is_active: true },
    });
  });

  // Delayed 200 response must not revive the session
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check session' })).not.toBeInTheDocument();
});

test('ignores delayed 401 response from previous session arriving after re-login so new session is preserved', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { access_token: 'first-token-111', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'first@example.com', is_active: true },
  });

  render(<App />);

  // Log in as first user
  await user.click(screen.getByRole('button', { name: 'Login' }));
  await user.type(screen.getByLabelText(/email/i), 'first@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  await screen.findByRole('status');

  // Trigger check with delayed promise for first user
  let resolveFirstCheck!: (value: CurrentUserResult) => void;
  const firstCheckPromise = new Promise<CurrentUserResult>((resolve) => {
    resolveFirstCheck = resolve;
  });
  vi.mocked(getCurrentUser).mockReturnValueOnce(firstCheckPromise);

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  // First user signs out
  await user.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();

  // Log in as second user
  vi.mocked(loginUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { access_token: 'second-token-222', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: true,
    status: 200,
    data: { user_id: 2, email: 'second@example.com', is_active: true },
  });

  await user.type(screen.getByLabelText(/email/i), 'second@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await openSessionScreen(user);

  const statusEl = await screen.findByRole('status');
  expect(statusEl).toHaveTextContent('Signed in as second@example.com');

  // Resolve the stale first check with 401
  await act(async () => {
    resolveFirstCheck({
      ok: false,
      kind: 'http',
      status: 401,
      message: 'Unauthorized',
    });
  });

  // Second user's session must stay intact, no 401 alert shown
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as second@example.com');
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Check session' })).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
