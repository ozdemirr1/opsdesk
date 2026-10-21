import { beforeEach, expect, test, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { loginUser, getCurrentUser, type CurrentUserResult } from './api/identity';

vi.mock('./api/identity', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/identity')>();
  return {
    ...actual,
    loginUser: vi.fn(),
    getCurrentUser: vi.fn(),
  };
});

beforeEach(() => {
  vi.mocked(loginUser).mockReset();
  vi.mocked(getCurrentUser).mockReset();
});

test('renders Tickets heading and table initially, no Login/Register headings, and Tickets button is selected', () => {
  render(<App />);

  // Check headings
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Register', level: 2 })).not.toBeInTheDocument();

  // Check initial table presence
  expect(screen.getByRole('table', { name: 'Ticket list' })).toBeInTheDocument();

  // Check the selected button
  expect(screen.getByRole('button', { name: 'Tickets' })).toHaveAttribute('aria-pressed', 'true');

  // Verify Sign out button is not visible initially
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check session' })).not.toBeInTheDocument();
});

test('navigates to Login screen and returns to Tickets screen showing the table again', async () => {
  const user = userEvent.setup();
  render(<App />);

  const loginBtn = screen.getByRole('button', { name: 'Login' });
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' });

  // Click the Login button
  await user.click(loginBtn);

  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('table', { name: 'Ticket list' })).not.toBeInTheDocument();

  // Verify form fields are rendered on the Login screen
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument();

  expect(loginBtn).toHaveAttribute('aria-pressed', 'true');

  // Click the Tickets button again
  await user.click(ticketsBtn);

  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('table', { name: 'Ticket list' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument();

  // Verify form fields are removed from the DOM
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();

  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'true');
});

test('shows only Register heading when navigated to Register, and form fields reset on screen return', async () => {
  const user = userEvent.setup();
  render(<App />);

  const registerBtn = screen.getByRole('button', { name: 'Register' });
  const loginBtn = screen.getByRole('button', { name: 'Login' });
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' });

  // Click the Register button
  await user.click(registerBtn);

  expect(screen.getByRole('heading', { name: 'Register', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('table', { name: 'Ticket list' })).not.toBeInTheDocument();

  // Form fields should be visible
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create account' });

  expect(emailInput).toBeInTheDocument();
  expect(passwordInput).toBeInTheDocument();
  expect(confirmPasswordInput).toBeInTheDocument();

  // Check button states
  expect(registerBtn).toHaveAttribute('aria-pressed', 'true');
  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'false');
  expect(loginBtn).toHaveAttribute('aria-pressed', 'false');

  // Type mismatched data (both >= 15 chars) into fields and submit
  await user.type(emailInput, 'draft@example.com');
  await user.type(passwordInput, 'draftPassword123');
  await user.type(confirmPasswordInput, 'differentPassword123');
  await user.click(submitBtn);

  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');

  // Switch to Tickets screen
  await user.click(ticketsBtn);

  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('table', { name: 'Ticket list' })).toBeInTheDocument();
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^Password/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^Confirm password/i)).not.toBeInTheDocument();

  // Return to Register screen and verify fields and feedback are reset
  await user.click(registerBtn);

  expect(screen.getByRole('heading', { name: 'Register', level: 2 })).toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Password/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Confirm password/i)).toHaveValue('');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('preserves authenticated session across screen transitions and does not leak to a new App instance', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  const { unmount } = render(<App />);

  const loginBtn = screen.getByRole('button', { name: 'Login' });
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' });

  // Navigate to Login screen
  await user.click(loginBtn);

  // Fill in credentials and submit
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  const submitBtn = screen.getByRole('button', { name: 'Sign in' });

  await user.type(emailInput, 'operator@example.com');
  await user.type(passwordInput, 'validPassword123');
  await user.click(submitBtn);

  // Verify status replaces form
  const statusEl = await screen.findByRole('status');
  expect(statusEl).toHaveTextContent('Signed in as operator@example.com');
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();

  // Switch to Tickets screen and verify status text is not displayed there
  await user.click(ticketsBtn);
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.queryByText('Signed in as operator@example.com')).not.toBeInTheDocument();

  // Return to Login screen: session should be preserved
  await user.click(loginBtn);
  expect(screen.getByRole('status')).toHaveTextContent('Signed in as operator@example.com');
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();

  // Mount a fresh App instance: should start without session
  unmount();
  render(<App />);

  const freshLoginBtn = screen.getByRole('button', { name: 'Login' });
  await user.click(freshLoginBtn);

  expect(screen.queryByText(/Signed in as/i)).not.toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
});

test('handles sign out flow: hides Sign out initially, signs out from Tickets, clears session, and allows re-login', async () => {
  const user = userEvent.setup();

  vi.mocked(loginUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { access_token: 'test-token-123', token_type: 'bearer' },
  });

  vi.mocked(getCurrentUser).mockResolvedValue({
    ok: true,
    status: 200,
    data: { user_id: 1, email: 'operator@example.com', is_active: true },
  });

  render(<App />);

  const loginBtn = screen.getByRole('button', { name: 'Login' });
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' });

  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

  // Log in
  await user.click(loginBtn);
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));

  await screen.findByRole('status');
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Navigate to Tickets
  await user.click(ticketsBtn);
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  const signOutBtn = screen.getByRole('button', { name: 'Sign out' });
  expect(signOutBtn).toBeInTheDocument();

  // Sign out
  await user.click(signOutBtn);

  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument();
  expect(loginBtn).toHaveAttribute('aria-pressed', 'true');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toHaveValue('');
  expect(screen.getByLabelText(/password/i)).toHaveValue('');
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

  // Switch to Tickets and back to Login: session must remain cleared
  await user.click(ticketsBtn);
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

  await user.click(loginBtn);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toHaveValue('');
  expect(screen.getByLabelText(/password/i)).toHaveValue('');
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

  // Sign in again
  await user.type(screen.getByLabelText(/email/i), 'operator@example.com');
  await user.type(screen.getByLabelText(/password/i), 'validPassword123');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));

  const newStatusEl = await screen.findByRole('status');
  expect(newStatusEl).toHaveTextContent('Signed in as operator@example.com');
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
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

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Tickets' }));

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

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Tickets' }));

  // Return network failure
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'network',
    status: null,
    message: 'Network request failed',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Switch to Login screen: session is preserved
  await user.click(screen.getByRole('button', { name: 'Login' }));
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

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Tickets' }));

  // Return 500 error
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'http',
    status: 500,
    message: 'Internal Server Error',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Switch to Login screen: session is preserved
  await user.click(screen.getByRole('button', { name: 'Login' }));
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

  await screen.findByRole('status');
  await user.click(screen.getByRole('button', { name: 'Tickets' }));

  // Return invalid response
  vi.mocked(getCurrentUser).mockResolvedValueOnce({
    ok: false,
    kind: 'invalid_response',
    status: 200,
    message: 'Invalid response format',
  });

  await user.click(screen.getByRole('button', { name: 'Check session' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify session. Please try again.');
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();

  // Switch to Login screen: session is preserved
  await user.click(screen.getByRole('button', { name: 'Login' }));
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

test('resets ticket search and status when leaving and returning to Tickets', async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.type(screen.getByRole('searchbox', { name: 'Search tickets' }), 'EMAIL');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'in_progress');
  expect(screen.getByRole('rowheader', { name: '#102' })).toBeVisible();
  expect(screen.queryByRole('rowheader', { name: '#101' })).not.toBeInTheDocument();
  expect(screen.queryByRole('rowheader', { name: '#103' })).not.toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: 'Login' }));
  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Tickets' }));
  expect(screen.getByRole('searchbox', { name: 'Search tickets' })).toHaveValue('');
  expect(screen.getByRole('combobox', { name: 'Status' })).toHaveValue('all');
  expect(screen.getAllByRole('rowheader')).toHaveLength(3);
  expect(screen.getByText('Tickets use mock data. Registration and login connect to the live API.'))
    .toBeVisible();
});
