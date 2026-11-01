import { afterEach, expect, test, vi } from 'vitest';
import { changeTicketPriority, type TicketResponse } from './tickets';
const ticket: TicketResponse = { ticket_id: 20, organization_id: 10, requester_membership_id: 1,
  creator_membership_id: 1, assignee_membership_id: null, title: 'Issue', description: 'Details',
  status: 'open', priority: 'high', created_at: '2026-10-30T10:00:00Z', updated_at: '2026-10-30T10:00:00Z' };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());
test('sends only priority with PUT and accepts an unchanged timestamp', async () => {
  const fetch = vi.fn().mockResolvedValue(json(ticket)); vi.stubGlobal('fetch', fetch);
  expect(await changeTicketPriority('token', 10, 20, 'high')).toEqual({ ok: true, status: 200, data: ticket });
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/organizations/10/tickets/20/priority'), expect.objectContaining({
    method: 'PUT', body: JSON.stringify({ priority: 'high' }),
    headers: { Authorization: 'Bearer token', 'Content-Type': 'application/json' },
  }));
});
test.each([{ ...ticket, organization_id: 99 }, { ...ticket, ticket_id: 99 }, { ...ticket, priority: 'low' },
  { ...ticket, status: 'closed' }, { ...ticket, status: 'resolved' }, { ...ticket, updated_at: 'invalid' }, null])(
  'rejects wrong-scope, inconsistent or malformed successful response', async value => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(value)));
    expect(await changeTicketPriority('token', 10, 20, 'high')).toMatchObject({ ok: false, kind: 'invalid_response' });
  });
test('does not accept a non-contract success status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(ticket, 201)));
  expect(await changeTicketPriority('token', 10, 20, 'high')).toMatchObject({ ok: false, kind: 'invalid_response' });
});
test('rejects invalid IDs, token and priority before fetch', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await changeTicketPriority('', 10, 20, 'high');
  await changeTicketPriority('token', 0, 20, 'high');
  await changeTicketPriority('token', 10, Number.MAX_SAFE_INTEGER + 1, 'high');
  await changeTicketPriority('token', 10, 20, 'invalid' as TicketResponse['priority']);
  expect(fetch).not.toHaveBeenCalled();
});
test('ignores success if scope cancellation happened during the request', async () => {
  let resolve!: (r: Response) => void;
  const fetch = vi.fn(() => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  const controller = new AbortController();
  const pending = changeTicketPriority('token', 10, 20, 'high', controller.signal);
  controller.abort(); resolve(json(ticket));
  expect(await pending).toMatchObject({ ok: false, kind: 'aborted' });
  expect(fetch).toHaveBeenCalledTimes(1);
});
