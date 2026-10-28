import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { getCurrentUser, loginUser } from './api/identity';
import { navigate, parseRoute } from './navigation';
import type { OrganizationContext } from './api/organizations';

vi.mock('./api/identity', async importOriginal => ({
  ...await importOriginal<typeof import('./api/identity')>(), loginUser: vi.fn(), getCurrentUser: vi.fn(),
}));
const alpha: OrganizationContext = {
  organization: { organization_id: 10, name: 'Alpha support', is_active: true },
  own_membership: { membership_id: 1, organization_id: 10, role: 'owner', is_active: true },
};
const beta: OrganizationContext = {
  organization: { organization_id: 20, name: 'Beta support', is_active: true },
  own_membership: { membership_id: 2, organization_id: 20, role: 'customer', is_active: true },
};
const ticket = (id = 1, org = 10, title = 'Private account issue') => ({
  ticket_id: id, organization_id: org, requester_membership_id: 1, creator_membership_id: 1,
  assignee_membership_id: null, title, description: 'First line.\nSecond line.', status: 'open', priority: 'high',
  created_at: '2026-10-27T10:00:00Z', updated_at: '2026-10-27T10:00:00Z',
});
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
function page<T>(items: T[], url: URL, total = items.length) {
  return json({ items, total_count: total, limit: Number(url.searchParams.get('limit') ?? 20), offset: Number(url.searchParams.get('offset') ?? 0) });
}
function deferred() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; });
  return { promise, resolve };
}
let handler: (url: URL, options: RequestInit) => Promise<Response> | Response;
const fetchMock = vi.fn<(url: string, options?: RequestInit) => Promise<Response>>();
beforeEach(() => {
  vi.mocked(loginUser).mockReset().mockResolvedValue({ ok: true, status: 200, data: { access_token: 'synthetic-test-token', token_type: 'bearer' } });
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue({ ok: true, status: 200, data: { user_id: 1, email: 'demo@example.com', is_active: true } });
  handler = url => {
    if (url.pathname.endsWith('/organizations')) return page([alpha, beta], url);
    if (/\/tickets\/\d+$/u.test(url.pathname)) return json(ticket(Number(url.pathname.split('/').at(-1))));
    return page([ticket()], url);
  };
  fetchMock.mockReset().mockImplementation(async (url, options = {}) => handler(new URL(url, 'http://localhost'), options));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
const user = () => userEvent.setup({ delay: null });
async function signIn() {
  const actor = user();
  await actor.type(screen.getByLabelText(/email/i), 'demo@example.com');
  await actor.type(screen.getByLabelText(/^password/i), 'demo-password-12345');
  await actor.click(screen.getByRole('button', { name: 'Sign in' }));
  await screen.findByRole('button', { name: 'Sign out' });
  return actor;
}
function start(path = '/organizations/10/tickets') {
  window.history.replaceState(null, '', `#${path}`);
  return render(<App />);
}
async function go(path: string) {
  await act(async () => { navigate(path); });
}

test('guards a deep detail URL, restores only that internal route after login, and guards reload', async () => {
  const view = start('/organizations/10/tickets/1');
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Workspaces' })).not.toBeInTheDocument();
  await signIn();
  expect(await screen.findByRole('region', { name: 'Ticket details' })).toHaveTextContent('Private account issue');
  expect(screen.queryByText(/MOCK TICKET/)).not.toBeInTheDocument();
  expect(window.location.hash).toBe('#/organizations/10/tickets/1');
  view.unmount();
  fetchMock.mockClear();
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test.each(['//evil.example', '/login?next=https://evil.example', '/organizations/9007199254740992/tickets', '/organizations/01/tickets', '/organizations/10/tickets/0'])(
  'rejects unknown/unsafe return destination %s', path => {
    expect(parseRoute(`#${path}`).screen).toBe('missing');
    start(path);
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

test('lists memberships with roles and navigates to the selected organization', async () => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha, beta], url) : page([ticket(8, 20, 'Beta ticket')], url);
  start('/organizations');
  const actor = await signIn();
  expect(await screen.findByText('Your role: customer')).toBeInTheDocument();
  await actor.click(screen.getByRole('link', { name: 'Open Beta support' }));
  expect(await screen.findByRole('button', { name: /View ticket #8/ })).toBeInTheDocument();
  expect(window.location.hash).toBe('#/organizations/20/tickets');
});

test('creates a workspace once with name only and follows server-owned context', async () => {
  let created = false;
  const pending = deferred();
  handler = (url, options) => {
    if (options.method === 'POST') { created = true; return pending.promise; }
    if (url.pathname.endsWith('/organizations')) return page(created ? [alpha] : [], url);
    return page([], url);
  };
  start('/organizations');
  const actor = await signIn();
  await screen.findByText('No workspaces yet. Create one below.');
  await actor.type(screen.getByLabelText('Workspace name'), 'Alpha support');
  await actor.dblClick(screen.getByRole('button', { name: 'Create workspace' }));
  const writes = fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({ name: 'Alpha support' });
  await act(async () => pending.resolve(json(alpha, 201)));
  expect(await screen.findByText('No tickets yet.')).toBeInTheDocument();
  expect(screen.getByText('Your role: owner')).toBeInTheDocument();
});

test('uncertain creation preserves input and does not retry automatically', async () => {
  handler = (url, options) => options.method === 'POST' ? Promise.reject(new Error('offline')) : page([], url);
  start('/organizations');
  const actor = await signIn();
  await actor.type(await screen.findByLabelText('Workspace name'), 'My workspace');
  await actor.click(screen.getByRole('button', { name: 'Create workspace' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Creation could not be confirmed');
  expect(screen.getByLabelText('Workspace name')).toHaveValue('My workspace');
  expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
});

test('suspended membership context never starts a Ticket read', async () => {
  handler = url => page([{ ...alpha, organization: { ...alpha.organization, is_active: false } }], url);
  start();
  await signIn();
  expect(await screen.findByRole('alert')).toHaveTextContent('suspended');
  expect(fetchMock.mock.calls.every(([url]) => !url.includes('/tickets'))).toBe(true);
});

test('a foreign workspace URL does not establish membership or read tickets', async () => {
  start('/organizations/99/tickets');
  await signIn();
  expect(await screen.findByRole('alert')).toHaveTextContent('Access is unavailable');
  expect(fetchMock.mock.calls.every(([url]) => !url.includes('/tickets'))).toBe(true);
});

test('organization change cancels old reads and clears filters even if old fetch ignores abort', async () => {
  const pending = deferred();
  let signal: AbortSignal | undefined;
  handler = (url, options) => {
    if (url.pathname.endsWith('/organizations')) return page([alpha, beta], url);
    if (url.pathname.includes('/10/')) {
      if (url.searchParams.has('q')) { signal = options.signal as AbortSignal; return pending.promise; }
      return page([ticket()], url);
    }
    return page([ticket(2, 20, 'Beta only')], url);
  };
  start();
  const actor = await signIn();
  await screen.findByRole('button', { name: /View ticket #1/ });
  await actor.type(screen.getByLabelText('Search ticket titles'), 'old search');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await waitFor(() => expect(signal).toBeDefined());
  await go('/organizations/20/tickets');
  expect(await screen.findByRole('button', { name: /Beta only/ })).toBeInTheDocument();
  expect(signal?.aborted).toBe(true);
  expect(screen.getByLabelText('Search ticket titles')).toHaveValue('');
  await act(async () => pending.resolve(json({ items: [ticket()], total_count: 1, offset: 0, limit: 20 })));
  expect(screen.queryByText('Private account issue')).not.toBeInTheDocument();
  expect(screen.getByText('Your role: customer')).toBeInTheDocument();
});

test('logout discards late private data and browser history cannot reopen it without login', async () => {
  const pending = deferred();
  let signal: AbortSignal | undefined;
  handler = (url, options) => {
    if (url.pathname.endsWith('/organizations')) return page([alpha], url);
    signal = options.signal as AbortSignal; return pending.promise;
  };
  start();
  const actor = await signIn();
  await screen.findByText('Loading tickets…');
  await actor.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(signal?.aborted).toBe(true);
  await act(async () => pending.resolve(json({ items: [ticket()], total_count: 1, offset: 0, limit: 20 })));
  expect(screen.queryByText('Private account issue')).not.toBeInTheDocument();
  await act(async () => { window.history.replaceState(null, '', '#/organizations/10/tickets'); window.dispatchEvent(new PopStateEvent('popstate')); });
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(screen.queryByText('Your role: owner')).not.toBeInTheDocument();
});

test('newer search wins over a late older response', async () => {
  const pending = deferred();
  handler = url => {
    if (url.pathname.endsWith('/organizations')) return page([alpha], url);
    if (url.searchParams.get('q') === 'first') return pending.promise;
    return page([ticket(2, 10, 'Latest result')], url);
  };
  start();
  const actor = await signIn();
  await screen.findByText('Latest result');
  await actor.type(screen.getByLabelText('Search ticket titles'), 'first');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  expect(screen.queryByText('Latest result')).not.toBeInTheDocument();
  await actor.clear(screen.getByLabelText('Search ticket titles'));
  await actor.type(screen.getByLabelText('Search ticket titles'), 'second');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await screen.findByText('Latest result');
  await act(async () => pending.resolve(json({ items: [ticket(1, 10, 'Stale result')], total_count: 1, offset: 0, limit: 20 })));
  expect(screen.queryByText('Stale result')).not.toBeInTheDocument();
});

test('paginates server results and resets offset when applying combined filters', async () => {
  handler = url => {
    if (url.pathname.endsWith('/organizations')) return page([alpha], url);
    if (url.searchParams.has('q')) return page([], url);
    const offset = Number(url.searchParams.get('offset'));
    return page(offset === 0 ? Array.from({ length: 20 }, (_, i) => ticket(i + 1, 10, `Issue ${i + 1}`)) : [ticket(21, 10, 'Last issue')], url, 21);
  };
  start();
  const actor = await signIn();
  await screen.findByText('Issue 1');
  await actor.click(screen.getByRole('button', { name: 'Next page' }));
  await screen.findByText('Last issue');
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  await actor.type(screen.getByLabelText('Search ticket titles'), '100% _!');
  await actor.selectOptions(screen.getByLabelText('Status'), 'closed');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await screen.findByText('No matching tickets.');
  const url = new URL(fetchMock.mock.calls.at(-1)![0], 'http://localhost');
  expect(url.searchParams.get('offset')).toBe('0');
  expect(url.searchParams.get('q')).toBe('100% _!');
  expect(url.searchParams.get('status')).toBe('closed');
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
});

test.each([401, 403, 404, 500])('handles detail HTTP %i without displaying stale data', async status => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url) : json({ error: {} }, status);
  start('/organizations/10/tickets/1');
  await signIn();
  if (status === 401) {
    await screen.findByRole('heading', { name: 'Login' });
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  } else {
    if (status === 403) await screen.findByRole('heading', { name: 'Workspace unavailable' });
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    if (status === 403) {
      expect(screen.queryByText('Your role: owner')).not.toBeInTheDocument();
    }
    if (status === 500) {
      handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url) : json(ticket());
      await user().click(screen.getByRole('button', { name: 'Retry' }));
      expect(await screen.findByRole('region', { name: 'Ticket details' })).toHaveTextContent('Private account issue');
    }
  }
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

test('malformed remote page is an error rather than empty data and preserves the session', async () => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url) : json({ items: [] });
  start();
  await signIn();
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load data');
  expect(screen.queryByText('No tickets yet.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
});

test('inactive session check removes selected private detail and role', async () => {
  start('/organizations/10/tickets/1');
  const actor = await signIn();
  await screen.findByRole('region', { name: 'Ticket details' });
  vi.mocked(getCurrentUser).mockResolvedValue({ ok: true, status: 200, data: { user_id: 1, email: 'demo@example.com', is_active: false } });
  await actor.click(screen.getByRole('button', { name: 'Check session' }));
  expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Ticket details' })).not.toBeInTheDocument();
  expect(screen.queryByText('Your role: owner')).not.toBeInTheDocument();
});

test('resolves membership on later pages before making a direct Ticket request', async () => {
  handler = url => {
    if (url.pathname.endsWith('/organizations')) {
      const offset = Number(url.searchParams.get('offset'));
      return page(offset === 0 ? Array.from({ length: 100 }, (_, i) => ({ ...alpha,
        organization: { ...alpha.organization, organization_id: i + 100 },
        own_membership: { ...alpha.own_membership, organization_id: i + 100 },
      })) : [alpha], url, 101);
    }
    return page([ticket()], url);
  };
  start();
  await signIn();
  expect(await screen.findByText('Private account issue')).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => url.includes('offset=100'))).toBe(true);
});


test('hides Workspaces before login, opens it after normal login, and hides it again on logout', async () => {
  start('/login');
  expect(screen.queryByRole('button', { name: 'Workspaces' })).not.toBeInTheDocument();
  const actor = await signIn();
  expect(await screen.findByRole('heading', { name: 'Workspaces' })).toBeInTheDocument();
  expect(window.location.hash).toBe('#/organizations');
  expect(screen.getByRole('button', { name: 'Workspaces' })).toHaveAttribute('aria-pressed', 'true');
  await actor.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.queryByRole('button', { name: 'Workspaces' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
});

test('failed login does not expose Workspaces or navigate to the directory', async () => {
  vi.mocked(loginUser).mockResolvedValue({ ok: false, kind: 'http', status: 401, message: 'Incorrect credentials.' });
  start('/login');
  const actor = user();
  await actor.type(screen.getByLabelText(/email/i), 'demo@example.com');
  await actor.type(screen.getByLabelText(/^password/i), 'demo-password-12345');
  await actor.click(screen.getByRole('button', { name: 'Sign in' }));
  await screen.findByRole('alert');
  expect(window.location.hash).toBe('#/login');
  expect(screen.queryByRole('button', { name: 'Workspaces' })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
