import type { TicketSummary } from '../types/ticket';

type TicketListProps = {
  tickets: TicketSummary[];
};

export default function TicketList({ tickets }: TicketListProps) {
  if (tickets.length === 0) {
    return <p>No tickets yet.</p>;
  }

  return (
    <ul role="list" aria-label="Ticket list" className="ticket-list">
      {tickets.map((ticket) => (
        <li key={ticket.ticketId} className="ticket-item">
          <h3>{ticket.title}</h3>
          <div className="ticket-details">
            <span>ID: #{ticket.ticketId}</span>
            <span className="status">Status: {ticket.status}</span>
            <span className="priority">Priority: {ticket.priority}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
