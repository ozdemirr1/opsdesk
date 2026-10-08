import type { TicketSummary } from '../types/ticket';

export const mockTickets: TicketSummary[] = [
  {
    ticketId: 101,
    title: 'Cannot access workspace',
    status: 'open',
    priority: 'high',
  },
  {
    ticketId: 102,
    title: 'Email notifications delayed',
    status: 'in_progress',
    priority: 'medium',
  },
  {
    ticketId: 103,
    title: 'Update support contact',
    status: 'resolved',
    priority: 'low',
  },
];
