import {
  isId, isRecord, isPage, matchesPage, validPageQuery, pageParams, withQuery,
  invalidRequest, requestResource, type Page, type PageQuery, type ResourceResult,
} from './resources';
import type { TicketPriority, TicketStatus, TicketSummary } from '../types/ticket';

/** Wire shape of the backend TicketResponse. Dates remain JSON strings. */
export type TicketResponse = {
  ticket_id: number;
  organization_id: number;
  requester_membership_id: number;
  creator_membership_id: number;
  assignee_membership_id: number | null;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  created_at: string;
  updated_at: string;
};

/** Project validated API data into display fields; this is not a JSON validator. */
export function toTicketSummary(ticket: Readonly<TicketResponse>): TicketSummary {
  return {
    ticketId: ticket.ticket_id,
    title: ticket.title,
    status: ticket.status,
    priority: ticket.priority,
    description: ticket.description,
  };
}

export type TicketQuery = PageQuery & {
  q?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  assignment?: 'assigned' | 'unassigned';
  assignee_membership_id?: number;
};
const statuses = ['open', 'in_progress', 'resolved', 'closed'];
const priorities = ['low', 'medium', 'high', 'urgent'];

/** Require a real calendar date and an explicit timezone; preserve the wire string. */
export function isTimestamp(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/u.exec(value);
  if (!parts || !Number.isFinite(Date.parse(value))) return false;
  const [, year, month, day, hour, minute, second, zone] = parts;
  const y = Number(year), m = Number(month), d = Number(day);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return y >= 1 && m >= 1 && m <= 12 && d >= 1 && d <= days[m - 1] &&
    Number(hour) <= 23 && Number(minute) <= 59 && Number(second) <= 59 &&
    (zone === 'Z' || (Number(zone.slice(1, 3)) <= 23 && Number(zone.slice(4)) <= 59));
}

export function isTicketResponse(value: unknown): value is TicketResponse {
  return isRecord(value) && isId(value.ticket_id) && isId(value.organization_id) &&
    isId(value.requester_membership_id) && isId(value.creator_membership_id) &&
    (value.assignee_membership_id === null || isId(value.assignee_membership_id)) &&
    typeof value.title === 'string' && value.title.trim().length > 0 &&
    typeof value.description === 'string' &&
    typeof value.status === 'string' && statuses.includes(value.status) &&
    typeof value.priority === 'string' && priorities.includes(value.priority) &&
    isTimestamp(value.created_at) && isTimestamp(value.updated_at);
}

export function isTicketPage(value: unknown): value is Page<TicketResponse> {
  return isPage(value, isTicketResponse) &&
    new Set(value.items.map(item => item.ticket_id)).size === value.items.length;
}

export function listTickets(
  token: string, organizationId: number, query: TicketQuery = {}, signal?: AbortSignal,
): Promise<ResourceResult<Page<TicketResponse>>> {
  if (!isId(organizationId) || !validPageQuery(query) ||
      (query.q !== undefined && (typeof query.q !== 'string' || [...query.q].length > 255 || [...query.q].some(char => ['\0', '\r', '\n', '\t'].includes(char)))) ||
      (query.status !== undefined && !statuses.includes(query.status)) ||
      (query.priority !== undefined && !priorities.includes(query.priority)) ||
      (query.assignment !== undefined && !['assigned', 'unassigned'].includes(query.assignment)) ||
      (query.assignee_membership_id !== undefined && !isId(query.assignee_membership_id)) ||
      (query.assignment === 'unassigned' && query.assignee_membership_id !== undefined)) {
    return Promise.resolve(invalidRequest());
  }
  const params = pageParams(query);
  // Do not lowercase, normalize or manually encode search text. The server owns matching.
  if (query.q !== undefined && query.q !== '') params.set('q', query.q);
  if (query.status !== undefined) params.set('status', query.status);
  if (query.priority !== undefined) params.set('priority', query.priority);
  if (query.assignment !== undefined) params.set('assignment', query.assignment);
  if (query.assignee_membership_id !== undefined) params.set('assignee_membership_id', String(query.assignee_membership_id));
  return requestResource(withQuery(`/organizations/${organizationId}/tickets`, params), token,
    (value): value is Page<TicketResponse> => isTicketPage(value) && matchesPage(value, query) &&
      value.items.every(ticket => ticket.organization_id === organizationId), { signal });
}

export function getTicket(
  token: string, organizationId: number, ticketId: number, signal?: AbortSignal,
): Promise<ResourceResult<TicketResponse>> {
  if (!isId(organizationId) || !isId(ticketId)) return Promise.resolve(invalidRequest());
  return requestResource(`/organizations/${organizationId}/tickets/${ticketId}`, token,
    (value): value is TicketResponse => isTicketResponse(value) &&
      value.organization_id === organizationId && value.ticket_id === ticketId, { signal });
}
