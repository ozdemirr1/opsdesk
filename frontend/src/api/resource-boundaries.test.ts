import { afterEach, expect, test, vi } from 'vitest';
import { API_BASE_URL } from './config';
import { createOrganization, getOrganization, isOrganizationContext, isOrganizationPage, listOrganizations } from './organizations';
import { getTicket, isTicketPage, isTicketResponse, listTickets, toTicketSummary, type TicketQuery } from './tickets';

const ticket = {
  ticket_id: 101, organization_id: 10, requester_membership_id: 20, creator_membership_id: 20,
  assignee_membership_id: null, title: 'Access problem', description: 'First line.\nSecond line.',
  status: 'open' as const, priority: 'high' as const,
  created_at: '2026-10-27T10:00:00.123456Z', updated_at: '2026-10-27T13:00:00+03:00',
};
const context = {
  organization: { organization_id: 10, name: 'Support', is_active: true },
  own_membership: { membership_id: 20, organization_id: 10, role: 'owner', is_active: true },
};
const page = <T,>(item: T) => ({ items: [item], total_count: 1, limit: 20, offset: 0 });
function respond(data: unknown, status = 200) {
  const fetch = vi.fn().mockResolvedValue({ ok: status < 300, status, json: async () => data });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());

test('validates before mapping without changing text or timestamps', async () => {
  respond(ticket);
  const result = await getTicket('synthetic-token', 10, 101);
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error('Expected validated ticket');
  expect(result.data).toEqual(ticket);
  expect(toTicketSummary(result.data).description).toBe(ticket.description);
});

test.each([
  null, [], {}, { ...ticket, ticket_id: '101' }, { ...ticket, ticket_id: 0 },
  { ...ticket, organization_id: Number.MAX_SAFE_INTEGER + 1 },
  { ...ticket, requester_membership_id: -1 }, { ...ticket, creator_membership_id: 1.5 },
  { ...ticket, assignee_membership_id: undefined }, { ...ticket, assignee_membership_id: false },
  { ...ticket, title: '' }, { ...ticket, description: null },
  { ...ticket, status: 'pending' }, { ...ticket, priority: 'critical' },
  { ...ticket, created_at: 'yesterday' }, { ...ticket, created_at: '2026-02-30T10:00:00Z' },
  { ...ticket, created_at: '2026-10-27T10:00:00' }, { ...ticket, updated_at: 123 },
  { ...ticket, created_at: '2026-10-27T24:00:00Z' },
])('rejects malformed Ticket wire data %#', value => expect(isTicketResponse(value)).toBe(false));

test('accepts lifecycle enums, leap dates, nullable assignment and empty descriptions', () => {
  for (const status of ['open', 'in_progress', 'resolved', 'closed']) {
    expect(isTicketResponse({ ...ticket, status, assignee_membership_id: 30, description: '', created_at: '2024-02-29T01:00:00Z' })).toBe(true);
  }
});

test.each([
  { ...page(ticket), total_count: -1 }, { ...page(ticket), total_count: Number.MAX_SAFE_INTEGER + 1 },
  { ...page(ticket), limit: 101 }, { ...page(ticket), offset: -1 },
  { ...page(ticket), items: [] }, { ...page(ticket), total_count: 0 },
  { ...page(ticket), items: [ticket, ticket], total_count: 2 },
  { ...page(ticket), items: [null] }, { ...page(ticket), limit: 0 },
])('rejects malformed or inconsistent page %#', value => expect(isTicketPage(value)).toBe(false));

test('empty and beyond-end pages retain the server total', async () => {
  const data = { items: [], total_count: 3, limit: 20, offset: 20 };
  respond(data);
  expect(await listTickets('synthetic-token', 10, { offset: 20 })).toEqual({ ok: true, status: 200, data });
  expect(isTicketPage({ ...data, total_count: 0, offset: 0 })).toBe(true);
});

test.each([
  { ...ticket, organization_id: 11 }, { ...ticket, ticket_id: 102 },
])('rejects a valid detail from a different requested resource %#', async data => {
  respond(data);
  expect(await getTicket('synthetic-token', 10, 101)).toMatchObject({ ok: false, kind: 'invalid_response' });
});

test('rejects another organization in a page and wrong pagination echo', async () => {
  respond(page({ ...ticket, organization_id: 11 }));
  expect(await listTickets('synthetic-token', 10)).toMatchObject({ ok: false, kind: 'invalid_response' });
  respond(page(ticket));
  expect(await listTickets('synthetic-token', 10, { limit: 5 })).toMatchObject({ ok: false, kind: 'invalid_response' });
});

test('encodes query exactly once and keeps token out of URL and body', async () => {
  const fetch = respond({ ...page(ticket), limit: 5 });
  const controller = new AbortController();
  const q = "İ %25_! &+' café";
  await listTickets('synthetic-token', 10, { q, status: 'open', priority: 'high', assignment: 'assigned', assignee_membership_id: 30, limit: 5, offset: 0 }, controller.signal);
  const [url, options] = fetch.mock.calls[0];
  const parsed = new URL(url, 'https://example.com');
  expect(url.split('?')[0]).toBe(`${API_BASE_URL.replace(/\/+$/u, '')}/organizations/10/tickets`);
  expect(Object.fromEntries(parsed.searchParams)).toEqual({ q, status: 'open', priority: 'high', assignment: 'assigned', assignee_membership_id: '30', limit: '5', offset: '0' });
  expect(url).not.toContain('synthetic-token');
  expect(options).toMatchObject({ method: 'GET', headers: { Authorization: 'Bearer synthetic-token' }, signal: controller.signal });
  expect(options.body).toBeUndefined();
});

test('omits empty search but leaves Unicode whitespace normalization to backend', async () => {
  const fetch = respond(page(ticket));
  await listTickets('synthetic-token', 10, { q: '' });
  expect(fetch.mock.calls[0][0]).not.toContain('?');
  await listTickets('synthetic-token', 10, { q: '\uFEFF' });
  expect(new URL(fetch.mock.calls[1][0], 'https://example.com').searchParams.get('q')).toBe('\uFEFF');
});

test.each([
  { limit: 0 }, { limit: 101 }, { offset: -1 }, { offset: Number.MAX_SAFE_INTEGER + 1 },
  { q: 'a'.repeat(256) }, { q: '\tvalue' }, { q: 'x\u0000' },
  { status: 'all' }, { assignment: 'unassigned', assignee_membership_id: 30 },
  { assignee_membership_id: 0 },
])('rejects invalid query locally without HTTP %#', async query => {
  const fetch = respond(page(ticket));
  expect(await listTickets('synthetic-token', 10, query as TicketQuery)).toMatchObject({ ok: false, kind: 'invalid_request' });
  expect(fetch).not.toHaveBeenCalled();
});

test('unsafe resource IDs and empty credentials never make requests', async () => {
  const fetch = respond(ticket);
  for (const id of [0, -1, NaN, Infinity, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    expect(await getTicket('synthetic-token', 10, id)).toMatchObject({ kind: 'invalid_request' });
    expect(await getOrganization('synthetic-token', id)).toMatchObject({ kind: 'invalid_request' });
  }
  expect(await listOrganizations('')).toMatchObject({ kind: 'invalid_request' });
  expect(fetch).not.toHaveBeenCalled();
});

test.each(['owner', 'admin', 'agent', 'customer'])('accepts API-backed role %s and suspended org context', role => {
  expect(isOrganizationContext({ organization: { ...context.organization, is_active: false }, own_membership: { ...context.own_membership, role } })).toBe(true);
});

test.each([
  { ...context, own_membership: { ...context.own_membership, organization_id: 11 } },
  { ...context, own_membership: { ...context.own_membership, membership_id: Number.MAX_SAFE_INTEGER + 1 } },
  { ...context, own_membership: { ...context.own_membership, role: 'superadmin' } },
  { ...context, own_membership: { ...context.own_membership, is_active: false } },
  { ...context, organization: { ...context.organization, is_active: 'true' } },
  { organization: context.organization },
])('rejects malformed or inconsistent membership context %#', value => expect(isOrganizationContext(value)).toBe(false));

test('organization lists use boolean filters and validated membership contexts', async () => {
  const suspended = { ...context, organization: { ...context.organization, is_active: false } };
  const fetch = respond(page(suspended));
  expect(await listOrganizations('synthetic-token', { is_active: false })).toMatchObject({ ok: true, data: page(suspended) });
  expect(fetch.mock.calls[0][0]).toContain('is_active=false');
  expect(await listOrganizations('synthetic-token', { is_active: true })).toMatchObject({ kind: 'invalid_response' });
  expect(isOrganizationPage({ ...page(context), items: [context, context], total_count: 2 })).toBe(false);
});

test('creation sends name only, requires 201 and server-derived active owner', async () => {
  const fetch = respond(context, 201);
  const input = { name: 'My organization', role: 'admin', user_id: 999 };
  expect(await createOrganization('synthetic-token', input)).toMatchObject({ ok: true, status: 201, data: context });
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ name: 'My organization' });
  respond(context, 200);
  expect(await createOrganization('synthetic-token', input)).toMatchObject({ kind: 'invalid_response' });
  respond({ ...context, own_membership: { ...context.own_membership, role: 'customer' } }, 201);
  expect(await createOrganization('synthetic-token', input)).toMatchObject({ kind: 'invalid_response' });
});

test('organization detail must match the requested ID', async () => {
  respond(context.organization);
  expect(await getOrganization('synthetic-token', 10)).toMatchObject({ ok: true });
  expect(await getOrganization('synthetic-token', 11)).toMatchObject({ kind: 'invalid_response' });
});

test.each([401, 403, 404, 422, 500, 503])('preserves HTTP failure %i instead of an empty page', async status => {
  const fetch = respond({ error: { code: 'unknown', message: 'private-server-data' } }, status);
  const result = await listTickets('synthetic-token', 10);
  expect(result).toMatchObject({ ok: false, kind: 'http', status });
  expect(JSON.stringify(result)).not.toContain('private-server-data');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('network and malformed JSON stay errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-details')));
  expect(await listOrganizations('synthetic-token')).toMatchObject({ kind: 'network' });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => { throw new Error('invalid-json'); } }));
  expect(await listOrganizations('synthetic-token')).toMatchObject({ kind: 'invalid_response' });
});

test('pre-cancelled requests do not fetch; late response after cancel is discarded', async () => {
  const controller = new AbortController();
  const fetch = respond(page(context));
  controller.abort();
  expect(await listOrganizations('synthetic-token', {}, controller.signal)).toMatchObject({ kind: 'aborted' });
  expect(fetch).not.toHaveBeenCalled();
  const late = new AbortController();
  vi.stubGlobal('fetch', vi.fn(async () => {
    late.abort();
    return { ok: true, status: 200, json: async () => page(ticket) };
  }));
  expect(await listTickets('synthetic-token', 10, {}, late.signal)).toMatchObject({ kind: 'aborted' });
});
