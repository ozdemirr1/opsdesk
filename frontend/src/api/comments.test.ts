import { afterEach, expect, test, vi } from 'vitest';
import { isCommentResponse, isCommentPage, listComments, postComment, validCommentContent } from './comments';
const comment = { comment_id: 1, author_membership_id: 2, content: 'Hello', created_at: '2026-10-30T10:00:00Z' };
const page = { items: [comment], total_count: 1, limit: 20, offset: 0 };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());

test.each([null, {}, { ...comment, comment_id: 0 }, { ...comment, author_membership_id: 1.5 },
  { ...comment, content: null }, { ...comment, content: '' }, { ...comment, content: 'x'.repeat(10001) },
  { ...comment, created_at: '2026-02-30T12:00:00Z' }])('rejects malformed comment %j', value => {
  expect(isCommentResponse(value)).toBe(false);
});
test('validates page identity, counts and duplicate IDs', () => {
  expect(isCommentResponse(comment)).toBe(true);
  expect(isCommentPage(page)).toBe(true);
  expect(isCommentPage({ ...page, total_count: 2 })).toBe(false);
  expect(isCommentPage({ ...page, items: [comment, comment], total_count: 2 })).toBe(false);
});
test.each(['x', '🙂'.repeat(10000), ' First\r\nSecond\tline ', '\ufeff'])('accepts valid content boundaries', content => {
  expect(validCommentContent(content)).toBe(true);
});
test.each(['', '\u0085', '\n\t ', '\x0btext', 'x\0', 'x'.repeat(10001), null, 42])('rejects invalid content', content => {
  expect(validCommentContent(content)).toBe(false);
});
test('posts content only and requires 201', async () => {
  const fetch = vi.fn().mockResolvedValue(json(comment, 201)); vi.stubGlobal('fetch', fetch);
  expect((await postComment('token', 10, 20, 'Hello')).ok).toBe(true);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/organizations/10/tickets/20/comments'), expect.objectContaining({
    method: 'POST', body: JSON.stringify({ content: 'Hello' }), headers: expect.objectContaining({ Authorization: 'Bearer token' }),
  }));
  fetch.mockResolvedValue(json(comment, 200));
  expect(await postComment('token', 10, 20, 'Hello')).toMatchObject({ ok: false, kind: 'invalid_response' });
});
test('reads requested page and rejects mismatched envelopes', async () => {
  const fetch = vi.fn().mockResolvedValue(json(page)); vi.stubGlobal('fetch', fetch);
  expect((await listComments('token', 10, 20)).ok).toBe(true);
  expect(await listComments('token', 10, 20, { offset: 20 })).toMatchObject({ ok: false, kind: 'invalid_response' });
});
test('invalid inputs never send requests', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await postComment('token', 0, 20, 'Hello');
  await postComment('token', 10, 20, '');
  await listComments('token', 10, 20, { limit: 101 });
  await listComments('', 10, 20);
  expect(fetch).not.toHaveBeenCalled();
});
test('late successful POST is ignored after cancellation', async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const controller = new AbortController();
  const pending = postComment('token', 10, 20, 'Hello', controller.signal);
  controller.abort(); resolve(json(comment, 201));
  expect(await pending).toMatchObject({ ok: false, kind: 'aborted' });
});
