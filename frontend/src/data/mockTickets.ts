import type { TicketSummary } from '../types/ticket';

export const mockTickets: TicketSummary[] = [
  {
    ticketId: 101,
    title: 'Cannot access workspace',
    status: 'open',
    priority: 'high',
    description: 'The requester cannot open the organization workspace.',
  },
  {
    ticketId: 102,
    title: 'Email notifications delayed',
    status: 'in_progress',
    priority: 'medium',
    description: 'Email notifications arrive later than expected.',
  },
  {
    ticketId: 103,
    title: 'Update support contact',
    status: 'resolved',
    priority: 'low',
    description: 'The organization needs to update its support contact.',
  },
];
