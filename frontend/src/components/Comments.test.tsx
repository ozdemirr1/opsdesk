import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Comments from './Comments';
const comment = (id = 1, content = 'Existing comment') => ({ comment_id: id, author_membership_id: 2, content, created_at: '2026-10-30T10:00:00Z' });
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const page = (items = [comment()], total = items.length, offset = 0) => json({ items, total_count: total, limit: 20, offset });
const props = () => ({ token: 'session-one', organizationId: 10, ticketId: 20, closed: false,
  onExpired: vi.fn(), onDenied: vi.fn(), refreshTicket: vi.fn() });
const fetch = vi.fn<(url: string, options?: RequestInit) => Promise<Response>>();
const user = () => userEvent.setup({ delay: null });
function deferred() { let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(done => { resolve = done; }); return { promise, resolve }; }
beforeEach(() => { fetch.mockReset().mockResolvedValue(page()); vi.stubGlobal('fetch', fetch); });
afterEach(() => vi.unstubAllGlobals());

test('loads history as plain text and posts content once, then clears draft and reloads', async () => {
  let posted = false;
  const pending = deferred();
  fetch.mockImplementation(async (_url, options) => {
    if (options?.method === 'POST') { posted = true; return pending.promise; }
    return posted ? page([comment(), comment(2, 'New comment')]) : page([comment(1, '<script>alert(1)</script>\nSecond line')]);
  });
  const view = render(<Comments {...props()} />);
  expect(await screen.findByText('<script>alert(1)</script> Second line', { exact: false })).toBeInTheDocument();
  expect(view.container.querySelector('script')).toBeNull();
  const actor = user();
  await actor.type(screen.getByLabelText('Add a comment'), 'New comment');
  await actor.dblClick(screen.getByRole('button', { name: 'Post comment' }));
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Posting…' })).toBeDisabled();
  await act(async () => pending.resolve(json(comment(2, 'New comment'), 201)));
  expect(await screen.findByText('Comment posted.')).toBeInTheDocument();
  expect(await screen.findByText('New comment', { selector: '.comment-list p' })).toBeInTheDocument();
  expect(screen.getByLabelText('Add a comment')).toHaveValue('');
});

test('closed ticket remains readable and has no posting form', async () => {
  render(<Comments {...props()} closed />);
  expect(await screen.findByText('Existing comment')).toBeInTheDocument();
  expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
  expect(screen.getByText(/read-only/)).toBeInTheDocument();
});

test('empty and paginated history are distinct', async () => {
  fetch.mockImplementation(async url => new URL(url, 'http://localhost').searchParams.get('offset') === '20'
    ? page([comment(21, 'Last comment')], 21, 20)
    : page(Array.from({ length: 20 }, (_, i) => comment(i + 1)), 21));
  render(<Comments {...props()} />);
  await screen.findByText('21 comments');
  await user().click(screen.getByRole('button', { name: 'Next comments' }));
  expect(await screen.findByText('Last comment')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Next comments' })).toBeDisabled();
  await user().click(screen.getByRole('button', { name: 'Previous comments' }));
  expect(await screen.findAllByText('Existing comment')).toHaveLength(20);
});

test('validation blocks blank/control content without sending a POST', async () => {
  render(<Comments {...props()} />);
  await screen.findByText('Existing comment');
  await user().click(screen.getByRole('button', { name: 'Post comment' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('1–10,000');
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
});

test.each([409, 422, 503, 500])('handles POST %s without clearing content or automatic retry', async status => {
  fetch.mockImplementation(async (_url, options) => options?.method === 'POST' ? json({}, status) : page());
  render(<Comments {...props()} />);
  await screen.findByText('Existing comment');
  const actor = user(); await actor.type(screen.getByLabelText('Add a comment'), 'Keep this draft');
  await actor.click(screen.getByRole('button', { name: 'Post comment' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(status === 409 ? 'no longer accepts' : status === 422 ? 'Check the comment' : 'could not be confirmed');
  expect(screen.getByLabelText('Add a comment')).toHaveValue('Keep this draft');
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  if (status === 409) expect(screen.getByRole('button', { name: 'Post comment' })).toBeDisabled();
});

test('network uncertainty preserves draft through manual list refresh', async () => {
  fetch.mockImplementation(async (_url, options) => { if (options?.method === 'POST') throw Error('offline'); return page(); });
  render(<Comments {...props()} />); await screen.findByText('Existing comment');
  const actor = user(); await actor.type(screen.getByLabelText('Add a comment'), 'Check before retry');
  await actor.click(screen.getByRole('button', { name: 'Post comment' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be confirmed');
  await actor.click(screen.getByRole('button', { name: 'Refresh comments' }));
  await screen.findByText('Existing comment');
  expect(screen.getByLabelText('Add a comment')).toHaveValue('Check before retry');
  expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
});

test.each([401, 403])('read denial %s hides form and invokes scope handler', async status => {
  fetch.mockResolvedValue(json({}, status)); const handlers = props();
  render(<Comments {...handlers} />);
  await waitFor(() => expect(status === 401 ? handlers.onExpired : status === 403 ? handlers.onDenied : handlers.refreshTicket).toHaveBeenCalled());
  expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
});

test.each([401, 403, 404])('write denial %s invokes scope handler', async status => {
  fetch.mockImplementation(async (_url, options) => options?.method === 'POST' ? json({}, status) : page());
  const handlers = props(); render(<Comments {...handlers} />); await screen.findByText('Existing comment');
  const actor = user(); await actor.type(screen.getByLabelText('Add a comment'), 'Message');
  await actor.click(screen.getByRole('button', { name: 'Post comment' }));
  expect(status === 401 ? handlers.onExpired : status === 403 ? handlers.onDenied : handlers.refreshTicket).toHaveBeenCalled();
});

test.each(['ticket', 'organization', 'session'])('scope change %s clears draft/history and ignores a late POST', async scope => {
  const pending = deferred();
  fetch.mockImplementation(async (_url, options) => options?.method === 'POST' ? pending.promise : page());
  const initial = props(); const view = render(<Comments {...initial} />); await screen.findByText('Existing comment');
  const actor = user(); await actor.type(screen.getByLabelText('Add a comment'), 'Old private draft');
  await actor.click(screen.getByRole('button', { name: 'Post comment' }));
  const postSignal = fetch.mock.calls.find(([, o]) => o?.method === 'POST')![1]!.signal!;
  fetch.mockResolvedValue(page([]));
  view.rerender(<Comments {...initial} {...(scope === 'ticket' ? { ticketId: 21 } : scope === 'organization' ? { organizationId: 11 } : { token: 'session-two' })} />);
  expect(screen.queryByText('Existing comment')).not.toBeInTheDocument();
  expect(postSignal.aborted).toBe(true);
  await act(async () => pending.resolve(json(comment(99, 'Old private draft'), 201)));
  await screen.findByText('No comments yet. Start the conversation.');
  expect(screen.getByLabelText('Add a comment')).toHaveValue('');
  expect(screen.queryByText('Comment posted.')).not.toBeInTheDocument();
});

test('unmount cancels a pending read and cannot expire a later session', async () => {
  const pending = deferred(); fetch.mockReturnValue(pending.promise);
  const handlers = props(); const view = render(<Comments {...handlers} />);
  const signal = fetch.mock.calls[0][1]!.signal!;
  view.unmount(); expect(signal.aborted).toBe(true);
  await act(async () => pending.resolve(json({}, 401)));
  expect(handlers.onExpired).not.toHaveBeenCalled();
});


test('missing comments route does not automatically reload the parent in a loop', async () => {
  fetch.mockResolvedValue(json({}, 404)); const handlers = props();
  render(<Comments {...handlers} />);
  await screen.findByRole('button', { name: 'Refresh ticket' });
  expect(handlers.refreshTicket).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
  await user().click(screen.getByRole('button', { name: 'Refresh ticket' }));
  expect(handlers.refreshTicket).toHaveBeenCalledOnce();
});
