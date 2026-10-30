import { isTimestamp } from './tickets';
import {
  isId, isRecord, isPage, matchesPage, validPageQuery, pageParams, withQuery,
  invalidRequest, requestResource, type Page, type PageQuery, type ResourceResult,
} from './resources';

export type CommentResponse = {
  comment_id: number; author_membership_id: number; content: string; created_at: string;
};

export function isCommentResponse(value: unknown): value is CommentResponse {
  return isRecord(value) && isId(value.comment_id) && isId(value.author_membership_id) &&
    typeof value.content === 'string' && [...value.content].length >= 1 &&
    [...value.content].length <= 10_000 && isTimestamp(value.created_at);
}
export function isCommentPage(value: unknown): value is Page<CommentResponse> {
  return isPage(value, isCommentResponse) &&
    new Set(value.items.map(item => item.comment_id)).size === value.items.length;
}

// The server owns normalization; send the original content and measure Unicode code points.
export function validCommentContent(content: unknown): content is string {
  if (typeof content !== 'string') return false;
  const normalized = content.replace(/\r\n?/gu, '\n');
  // Python str.strip() also trims NEL, but preserves BOM (unlike JS trim()).
  const chars = [...normalized];
  const edgeSpace = (char: string) => {
    const code = char.codePointAt(0)!;
    return (code >= 9 && code <= 13) || (code >= 28 && code <= 32) ||
      [133, 160, 5760, 8232, 8233, 8239, 8287, 12288].includes(code) ||
      (code >= 8192 && code <= 8202);
  };
  let start = 0, end = chars.length;
  while (start < end && edgeSpace(chars[start])) start++;
  while (end > start && edgeSpace(chars[end - 1])) end--;
  const length = end - start;
  return ![...normalized].some(char => char.codePointAt(0)! < 32 && char !== '\n' && char !== '\t') &&
    length >= 1 && length <= 10_000;
}
const path = (organizationId: number, ticketId: number) =>
  `/organizations/${organizationId}/tickets/${ticketId}/comments`;
export function listComments(token: string, organizationId: number, ticketId: number,
  query: PageQuery = {}, signal?: AbortSignal): Promise<ResourceResult<Page<CommentResponse>>> {
  if (!isId(organizationId) || !isId(ticketId) || !validPageQuery(query)) return Promise.resolve(invalidRequest());
  return requestResource(withQuery(path(organizationId, ticketId), pageParams(query)), token,
    (value): value is Page<CommentResponse> => isCommentPage(value) && matchesPage(value, query), { signal });
}
export function postComment(token: string, organizationId: number, ticketId: number,
  content: string, signal?: AbortSignal): Promise<ResourceResult<CommentResponse>> {
  if (!isId(organizationId) || !isId(ticketId) || !validCommentContent(content)) return Promise.resolve(invalidRequest());
  return requestResource(path(organizationId, ticketId), token, isCommentResponse,
    { body: { content }, expectedStatus: 201, signal });
}
