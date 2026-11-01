import { afterEach, expect, test, vi } from 'vitest';
import { createTicket, validateTicketInput, type CreateTicketInput } from './tickets';

const input: CreateTicketInput = { title: 'Printer issue', description: 'First line.\nSecond line.', priority: 'medium' };
const response = { ticket_id: 7, organization_id: 10, requester_membership_id: 2, creator_membership_id: 2,
  assignee_membership_id: null, ...input, status: 'open', created_at: '2026-10-31T10:00:00Z', updated_at: '2026-10-31T10:00:00Z' };
const json = (body: unknown, status = 201) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
afterEach(() => vi.unstubAllGlobals());

test('posts normalized content only, with bearer authentication, and accepts 201', async () => {
  const fetcher = vi.fn().mockResolvedValue(json(response)); vi.stubGlobal('fetch', fetcher);
  const extra = { ...input, title: '  Printer issue ', requester_membership_id: 999, status: 'closed' };
  expect(await createTicket('test-token', 10, extra)).toMatchObject({ ok: true, status: 201, data: response });
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toContain('/organizations/10/tickets');
  expect(options.method).toBe('POST');
  expect(options.headers.Authorization).toBe('Bearer test-token');
  expect(JSON.parse(options.body)).toEqual(input);
});

test.each([
  { title: '' }, { title: '  ' }, { title: 'a\nb' }, { title: 'a\tb' }, { title: 'a\0b' },
  { title: 'a'.repeat(256) }, { description: '' }, { description: ' \n ' },
  { description: 'a\0b' }, { description: 'a'.repeat(10001) }, { priority: 'invalid' },
])('rejects invalid creation input without a network request: %j', async patch => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  expect(await createTicket('test-token', 10, { ...input, ...patch } as CreateTicketInput)).toMatchObject({ ok: false, kind: 'invalid_request' });
  expect(fetcher).not.toHaveBeenCalled();
});

test('counts Unicode code points and preserves internal multiline description', () => {
  expect(validateTicketInput({ ...input, title: '😀'.repeat(255), description: '😀'.repeat(10000) })).toEqual({});
  expect(validateTicketInput({ ...input, title: '😀'.repeat(256) })).toHaveProperty('title');
});

test.each([{ organization_id: 20 }, { ticket_id: 0 }, { status: 'closed' }, { priority: 'urgent' },
  { title: 'Different title' }, { description: 'Different description' }, { requester_membership_id: 3 }, { assignee_membership_id: 3 }])(
  'rejects mismatched create response: %j', async patch => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ ...response, ...patch })));
    expect(await createTicket('test-token', 10, input)).toMatchObject({ ok: false, kind: 'invalid_response' });
  },
);
test('does not treat an unexpected 200 as confirmed creation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(response, 200)));
  expect(await createTicket('test-token', 10, input)).toMatchObject({ ok: false, kind: 'invalid_response' });
});
test('aborted creation never publishes a late success even if fetch ignores cancellation', async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
  const controller = new AbortController();
  const result = createTicket('test-token', 10, input, controller.signal);
  controller.abort(); finish(json(response));
  expect(await result).toMatchObject({ ok: false, kind: 'aborted' });
});
