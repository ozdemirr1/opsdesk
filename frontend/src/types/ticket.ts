export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed';

export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';

export type TicketSummary = {
  ticketId: number;
  title: string;
  status: TicketStatus;
  priority: TicketPriority;
};
