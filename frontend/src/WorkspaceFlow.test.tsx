import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  fetchMock.mockReset().mockImplementation(async (url, options = {}) => {
    const target = new URL(url, 'http://localhost');
    if (target.pathname.endsWith('/comments')) return page([], target);
    return handler(target, options);
  });
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


test.each(['sign-out', 'unauthorized', 'inactive'] as const)(
  'clears real dashboard filters and selection across %s and re-login', async reason => {
    start();
    const actor = await signIn();
    await screen.findByRole('button', { name: /View ticket #1/ });
    await actor.type(screen.getByLabelText('Search ticket titles'), 'Private');
    await actor.selectOptions(screen.getByLabelText('Status'), 'open');
    await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
    await actor.click(await screen.findByRole('button', { name: /View ticket #1/ }));
    await screen.findByRole('region', { name: 'Ticket details' });
    if (reason === 'sign-out') {
      await actor.click(screen.getByRole('button', { name: 'Sign out' }));
    } else {
      vi.mocked(getCurrentUser).mockResolvedValueOnce(reason === 'unauthorized'
        ? { ok: false, kind: 'http', status: 401, message: 'Authentication required.' }
        : { ok: true, status: 200, data: { user_id: 1, email: 'demo@example.com', is_active: false } });
      await actor.click(screen.getByRole('button', { name: 'Check session' }));
    }
    await screen.findByRole('heading', { name: 'Login' });
    expect(screen.queryByRole('region', { name: 'Ticket details' })).not.toBeInTheDocument();
    expect(screen.queryByText('Your role: owner')).not.toBeInTheDocument();
    await go('/');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    await signIn();
    await actor.click(await screen.findByRole('link', { name: 'Open Alpha support' }));
    await screen.findByRole('table');
    expect(screen.getByLabelText('Search ticket titles')).toHaveValue('');
    expect(screen.getByLabelText('Status')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.queryByRole('region', { name: 'Ticket details' })).not.toBeInTheDocument();
  },
);


test.each(['owner', 'admin', 'agent', 'customer'] as const)('priority control follows API membership role %s', async role => {
  handler = url => url.pathname.endsWith('/organizations')
    ? page([{ ...alpha, own_membership: { ...alpha.own_membership, role } }], url) : json(ticket());
  start('/organizations/10/tickets/1'); await signIn();
  await screen.findByRole('region', { name: 'Ticket details' });
  expect(screen.queryByRole('button', { name: 'Save priority' }) !== null).toBe(role !== 'customer');
});

test.each(['resolved', 'closed'])('priority control is unavailable for %s tickets', async status => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url) : json({ ...ticket(), status });
  start('/organizations/10/tickets/1'); await signIn();
  await screen.findByRole('region', { name: 'Ticket details' });
  expect(screen.queryByRole('button', { name: 'Save priority' })).not.toBeInTheDocument();
  expect(screen.getByText('Priority cannot be changed on resolved or closed tickets.')).toBeInTheDocument();
});

test('priority success updates detail without losing a comment draft and prevents duplicate PUTs', async () => {
  const pending = deferred();
  handler = (url, options) => options.method === 'PUT' ? pending.promise
    : url.pathname.endsWith('/organizations') ? page([alpha], url) : json(ticket());
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await waitFor(() => expect(screen.getByLabelText('Add a comment')).toBeEnabled());
  await actor.type(screen.getByLabelText('Add a comment'), 'Keep comment draft');
  await actor.selectOptions(screen.getByLabelText('Priority'), 'urgent');
  await actor.dblClick(screen.getByRole('button', { name: 'Save priority' }));
  expect(fetchMock.mock.calls.filter(([, o]) => o?.method === 'PUT')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Saving priority…' })).toBeDisabled();
  await act(async () => pending.resolve(json({ ...ticket(), priority: 'urgent', updated_at: '2026-10-30T12:00:00Z' })));
  expect(await screen.findByText('Priority updated.')).toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'Ticket details' })).getByText('urgent')).toBeInTheDocument();
  expect(screen.getByLabelText('Add a comment')).toHaveValue('Keep comment draft');
});

test('same priority still reaches backend authorization and shows a confirmed no-op', async () => {
  handler = (url, options) => options.method === 'PUT' ? json(ticket())
    : url.pathname.endsWith('/organizations') ? page([alpha], url) : json(ticket());
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await actor.click(await screen.findByRole('button', { name: 'Save priority' }));
  expect(await screen.findByText('Priority unchanged.')).toBeInTheDocument();
  const writes = fetchMock.mock.calls.filter(([, o]) => o?.method === 'PUT');
  expect(writes).toHaveLength(1);
  expect(JSON.parse(String(writes[0][1]?.body))).toEqual({ priority: 'high' });
});

test.each([401, 403, 404])('priority write denial %s clears unavailable private detail', async status => {
  handler = (url, options) => options.method === 'PUT' ? json({}, status)
    : url.pathname.endsWith('/organizations') ? page([alpha], url) : json(ticket());
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await actor.click(await screen.findByRole('button', { name: 'Save priority' }));
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Ticket details' })).not.toBeInTheDocument());
  expect(screen.queryByRole('button', { name: 'Save priority' })).not.toBeInTheDocument();
  if (status === 401) expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
});

test.each([409, 500, 503, 'network', 'malformed'] as const)('priority failure %s requires manual refresh without retry or optimistic update', async failure => {
  let changed = false;
  handler = (url, options) => {
    if (options.method === 'PUT') {
      changed = true;
      if (failure === 'network') throw Error('offline');
      return failure === 'malformed' ? json({ unexpected: true }) : json({}, failure);
    }
    return url.pathname.endsWith('/organizations') ? page([alpha], url)
      : json({ ...ticket(), status: changed ? 'closed' : 'open' });
  };
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await actor.selectOptions(await screen.findByLabelText('Priority'), 'urgent');
  await actor.click(screen.getByRole('button', { name: 'Save priority' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(failure === 409 ? 'state has changed' : 'could not be confirmed');
  expect(screen.getByRole('button', { name: 'Save priority' })).toBeDisabled();
  expect(within(screen.getByRole('region', { name: 'Ticket details' })).getByText('high')).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([, o]) => o?.method === 'PUT')).toHaveLength(1);
  await actor.click(screen.getByRole('button', { name: 'Refresh ticket' }));
  expect(await screen.findByText('Priority cannot be changed on resolved or closed tickets.')).toBeInTheDocument();
});

test('priority validation failure retains selection and permits manual correction', async () => {
  handler = (url, options) => options.method === 'PUT' ? json({}, 422)
    : url.pathname.endsWith('/organizations') ? page([alpha], url) : json(ticket());
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await actor.selectOptions(await screen.findByLabelText('Priority'), 'urgent');
  await actor.click(screen.getByRole('button', { name: 'Save priority' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Select a valid priority');
  expect(screen.getByLabelText('Priority')).toHaveValue('urgent');
  expect(screen.getByRole('button', { name: 'Save priority' })).toBeEnabled();
});

test.each(['ticket', 'organization', 'session'])('priority pending request cannot affect the new %s scope', async scope => {
  const pending = deferred();
  handler = (url, options) => {
    if (options.method === 'PUT') return pending.promise;
    if (url.pathname.endsWith('/organizations')) return page([alpha, beta], url);
    return url.pathname.includes('/20/tickets') ? json(ticket(2, 20, 'Beta private ticket'))
      : json(ticket(Number(url.pathname.split('/').at(-1)), 10));
  };
  start('/organizations/10/tickets/1'); const actor = await signIn();
  await actor.selectOptions(await screen.findByLabelText('Priority'), 'urgent');
  await actor.click(screen.getByRole('button', { name: 'Save priority' }));
  const signal = fetchMock.mock.calls.find(([, o]) => o?.method === 'PUT')![1]!.signal!;
  if (scope === 'session') {
    await actor.click(screen.getByRole('button', { name: 'Sign out' }));
    await signIn();
  } else await go(scope === 'ticket' ? '/organizations/10/tickets/2' : '/organizations/20/tickets/2');
  await waitFor(() => expect(signal.aborted).toBe(true));
  await act(async () => pending.resolve(scope === 'session' ? json({}, 401) : json({ ...ticket(), priority: 'urgent' })));
  expect(screen.queryByText('Priority updated.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
  if (scope === 'organization') {
    await screen.findByText('Beta private ticket');
    expect(screen.queryByRole('button', { name: 'Save priority' })).not.toBeInTheDocument();
  }
  if (scope === 'ticket') expect(await screen.findByLabelText('Priority')).toHaveValue('high');
});

async function openTicketForm() {
  const actor = await signIn();
  await actor.click(await screen.findByRole('button', { name: 'New ticket' }));
  expect(screen.getByRole('dialog', { name: 'Create ticket' })).toBeInTheDocument();
  expect(screen.getByLabelText('Title')).toHaveFocus();
  return actor;
}
async function fillTicketForm(actor: ReturnType<typeof user>) {
  await actor.type(screen.getByLabelText('Title'), 'Printer issue');
  await actor.type(screen.getByLabelText('Description'), 'First line.\nSecond line.');
  await actor.selectOptions(screen.getByLabelText('Priority'), 'high');
}
const ticketWrites = () => fetchMock.mock.calls.filter(([url, options]) => url.includes('/tickets') && options?.method === 'POST');

test.each([10, 20])('member in workspace %s creates once and navigates to canonical detail with scoped success', async org => {
  const pending = deferred();
  handler = (url, options) => {
    if (url.pathname.endsWith('/organizations')) return page([alpha, beta], url);
    if (options.method === 'POST') return pending.promise;
    if (url.pathname.endsWith('/tickets/7')) return json(ticket(7, org, 'Printer issue'));
    return page([], url);
  };
  start(`/organizations/${org}/tickets`);
  const actor = await openTicketForm();
  await fillTicketForm(actor);
  await actor.dblClick(screen.getByRole('button', { name: 'Create ticket' }));
  expect(ticketWrites()).toHaveLength(1);
  expect(ticketWrites()[0][0]).toContain(`/organizations/${org}/tickets`);
  expect(JSON.parse(String(ticketWrites()[0][1]?.body))).toEqual({ title: 'Printer issue', description: 'First line.\nSecond line.', priority: 'high' });
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  await act(async () => pending.resolve(json(ticket(7, org, 'Printer issue'), 201)));
  expect(await screen.findByRole('region', { name: 'Ticket details' })).toHaveTextContent('Printer issue');
  expect(window.location.hash).toBe(`#/organizations/${org}/tickets/7`);
  expect(screen.getByText('Ticket #7 created successfully.')).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await go(`/organizations/${org}/tickets`);
  await go(`/organizations/${org}/tickets/7`);
  expect(screen.queryByText('Ticket #7 created successfully.')).not.toBeInTheDocument();
});

test('empty fields block POST and cancelling restores focus to New ticket', async () => {
  start(); const actor = await openTicketForm();
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  expect(ticketWrites()).toHaveLength(0);
  expect(screen.getByLabelText('Title')).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByLabelText('Title')).toHaveFocus();
  await actor.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'New ticket' })).toHaveFocus();
});

test('422 keeps the draft editable and never displays unsafe server detail', async () => {
  const oldHandler = handler;
  handler = (url, options) => options.method === 'POST' ? json({ detail: 'secret database diagnostic' }, 422) : oldHandler(url, options);
  start(); const actor = await openTicketForm(); await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Check the title, description and priority');
  expect(screen.getByLabelText('Title')).toHaveValue('Printer issue');
  expect(screen.getByLabelText('Title')).toBeEnabled();
  expect(screen.queryByText(/secret database/)).not.toBeInTheDocument();
});

test.each([401, 403, 404])('creation response %s clears the form and protected context', async status => {
  const oldHandler = handler;
  handler = (url, options) => options.method === 'POST' ? json({}, status) : oldHandler(url, options);
  start(); const actor = await openTicketForm(); await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  if (status === 401) expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  else expect(screen.getByRole('heading', { name: 'Workspace unavailable' })).toBeInTheDocument();
  expect(screen.queryByText('Printer issue')).not.toBeInTheDocument();
});

test.each(['network', 'invalid', 'server'])('uncertain %s result prevents resend and offers an unfiltered list check', async failure => {
  const oldHandler = handler;
  handler = (url, options) => options.method === 'POST'
    ? failure === 'network' ? Promise.reject(new Error('offline')) : json({}, failure === 'server' ? 503 : 201)
    : oldHandler(url, options);
  start(); const actor = await signIn();
  await actor.type(await screen.findByLabelText('Search ticket titles'), 'old search');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await actor.click(screen.getByRole('button', { name: 'New ticket' }));
  await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Creation could not be confirmed');
  expect(screen.getByLabelText('Title')).toHaveValue('Printer issue');
  expect(screen.getByLabelText('Title')).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Create ticket' })).not.toBeInTheDocument();
  expect(ticketWrites()).toHaveLength(1);
  await actor.click(screen.getByRole('button', { name: 'Check ticket list' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Search ticket titles')).toHaveValue('');
  await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).not.toContain('q='));
});

test.each(['workspace', 'logout'])('%s during creation discards late success and aborts request', async change => {
  const pending = deferred(); let signal: AbortSignal | undefined;
  const oldHandler = handler;
  handler = (url, options) => {
    if (options.method === 'POST') { signal = options.signal as AbortSignal; return pending.promise; }
    return oldHandler(url, options);
  };
  start(); const actor = await openTicketForm(); await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  if (change === 'workspace') await go('/organizations/20/tickets');
  else await actor.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(signal?.aborted).toBe(true);
  await act(async () => pending.resolve(json(ticket(7, 10, 'Printer issue'), 201)));
  expect(window.location.hash).not.toBe('#/organizations/10/tickets/7');
  expect(screen.queryByText('Ticket #7 created successfully.')).not.toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('a stalled create request times out as uncertain and ignores a later success', async () => {
  const pending = deferred(); let signal: AbortSignal | undefined;
  const oldHandler = handler;
  handler = (url, options) => {
    if (options.method === 'POST') { signal = options.signal as AbortSignal; return pending.promise; }
    return oldHandler(url, options);
  };
  start(); const actor = await openTicketForm(); await fillTicketForm(actor);
  vi.useFakeTimers();
  try {
    fireEvent.click(screen.getByRole('button', { name: 'Create ticket' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(signal?.aborted).toBe(true);
    expect(screen.getByRole('alert')).toHaveTextContent('Creation could not be confirmed');
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();
    await act(async () => pending.resolve(json(ticket(7, 10, 'Printer issue'), 201)));
    expect(screen.queryByText('Ticket #7 created successfully.')).not.toBeInTheDocument();
    expect(ticketWrites()).toHaveLength(1);
  } finally { vi.useRealTimers(); }
});

test('empty workspace directory action focuses the creation field without changing route', async () => {
  handler = url => page([], url);
  start('/organizations'); const actor = await signIn();
  await actor.click(await screen.findByRole('button', { name: 'Name your workspace' }));
  expect(screen.getByLabelText('Workspace name')).toHaveFocus();
  expect(window.location.hash).toBe('#/organizations');
});

test('empty ticket action opens the modal and cancellation restores its own trigger', async () => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url) : page([], url);
  start(); const actor = await signIn();
  await actor.click(await screen.findByRole('button', { name: 'Create your first ticket' }));
  expect(screen.getByLabelText('Title')).toHaveFocus();
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Create your first ticket' })).toHaveFocus();
  expect(ticketWrites()).toHaveLength(0);
});

test('no-match recovery clears applied filters and returns keyboard focus to search', async () => {
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url)
    : url.searchParams.has('q') || url.searchParams.has('status') ? page([], url) : page([ticket()], url);
  start(); const actor = await signIn();
  await actor.type(await screen.findByLabelText('Search ticket titles'), 'missing');
  await actor.selectOptions(screen.getByLabelText('Status'), 'closed');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await actor.click(await screen.findByRole('button', { name: 'Reset search and status' }));
  expect(screen.getByLabelText('Search ticket titles')).toHaveFocus();
  expect(screen.getByLabelText('Search ticket titles')).toHaveValue('');
  expect(screen.getByLabelText('Status')).toHaveValue('');
  expect(await screen.findByRole('button', { name: /View ticket #1/ })).toBeInTheDocument();
});

test('a now-empty ticket page can return to page one while preserving search', async () => {
  handler = url => {
    if (url.pathname.endsWith('/organizations')) return page([alpha], url);
    if (url.searchParams.get('offset') === '20') return page([], url, 1);
    return page(Array.from({length:20}, (_, i) => ticket(i + 1)), url, 21);
  };
  start(); const actor = await signIn();
  await actor.type(await screen.findByLabelText('Search ticket titles'), 'Private');
  await actor.click(screen.getByRole('button', { name: 'Apply filters' }));
  await actor.click(await screen.findByRole('button', { name: 'Next page' }));
  await actor.click(await screen.findByRole('button', { name: 'First ticket page' }));
  expect(await screen.findByRole('button', { name: /View ticket #1:/ })).toBeInTheDocument();
  const lastUrl = new URL(fetchMock.mock.calls.at(-1)![0], 'http://localhost');
  expect(lastUrl.searchParams.get('offset')).toBe('0');
  expect(lastUrl.searchParams.get('q')).toBe('Private');
});

test('loading and failure never masquerade as empty tickets; retry recovers', async () => {
  const pending = deferred(); let recovered = false;
  handler = url => url.pathname.endsWith('/organizations') ? page([alpha], url)
    : recovered ? page([], url) : pending.promise;
  start(); const actor = await signIn();
  expect(await screen.findByText('Loading tickets…')).toHaveAttribute('role', 'status');
  expect(screen.queryByText('No tickets yet.')).not.toBeInTheDocument();
  await act(async () => pending.resolve(json({detail:'private diagnostic'}, 503)));
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load data');
  expect(screen.queryByText('No tickets yet.')).not.toBeInTheDocument();
  expect(screen.queryByText('private diagnostic')).not.toBeInTheDocument();
  recovered = true;
  await actor.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('No tickets yet.')).toBeInTheDocument();
});

test('Escape cannot hide a pending create and validation errors are announced', async () => {
  const pending = deferred(); const oldHandler = handler;
  handler = (url, options) => options.method === 'POST' ? pending.promise : oldHandler(url, options);
  start(); const actor = await openTicketForm();
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Check the highlighted fields');
  await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  await act(async () => pending.resolve(json({}, 422)));
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('integrated owner flow creates, reads, comments, changes priority and clears private UI on logout', async () => {
  let saved = ticket(9, 10, 'Printer issue');
  const comments: {comment_id:number;author_membership_id:number;content:string;created_at:string}[] = [];
  fetchMock.mockImplementation(async (raw, options = {}) => {
    const url = new URL(raw, 'http://localhost');
    if (url.pathname.endsWith('/organizations')) return page([alpha], url);
    if (url.pathname.endsWith('/comments')) {
      if (options.method === 'POST') {
        const comment = {comment_id:1,author_membership_id:1,content:JSON.parse(String(options.body)).content,created_at:'2026-11-01T10:00:00Z'};
        comments.push(comment); return json(comment, 201);
      }
      return page(comments, url);
    }
    if (url.pathname.endsWith('/priority')) {
      saved = {...saved, priority:JSON.parse(String(options.body)).priority}; return json(saved);
    }
    if (options.method === 'POST') return json(saved, 201);
    if (url.pathname.endsWith('/tickets/9')) return json(saved);
    return page([], url);
  });
  start(); const actor = await openTicketForm(); await fillTicketForm(actor);
  await actor.click(screen.getByRole('button', { name: 'Create ticket' }));
  await screen.findByRole('region', { name: 'Ticket details' });
  await actor.click(await screen.findByRole('button', { name: 'Write a comment' }));
  expect(screen.getByLabelText('Add a comment')).toHaveFocus();
  await actor.type(screen.getByLabelText('Add a comment'), 'Reproduced the issue.');
  await actor.click(screen.getByRole('button', { name: 'Post comment' }));
  expect(await screen.findByText('Comment posted.')).toBeInTheDocument();
  expect(await screen.findByText('Reproduced the issue.')).toBeInTheDocument();
  await actor.selectOptions(screen.getByLabelText('Priority', {exact:true}), 'urgent');
  await actor.click(screen.getByRole('button', { name: 'Save priority' }));
  expect(await screen.findByText('Priority updated.')).toBeInTheDocument();
  await actor.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  expect(screen.queryByText('Reproduced the issue.')).not.toBeInTheDocument();
  expect(screen.queryByText('Printer issue')).not.toBeInTheDocument();
});
