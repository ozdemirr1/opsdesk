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
