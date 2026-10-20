import type { TicketSummary } from '../types/ticket';
import StatusBadge from './StatusBadge';

type TicketTableProps = {
  tickets: TicketSummary[];
};

export default function TicketTable({ tickets }: TicketTableProps) {
  if (tickets.length === 0) {
    return <p>No tickets yet.</p>;
  }

  return (
    <div className="ticket-table-container" role="region" aria-label="Ticket table" tabIndex={0}>
      <table className="ticket-table">
        <caption>Ticket list</caption>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Title</th>
            <th scope="col">Status</th>
            <th scope="col">Priority</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr key={ticket.ticketId}>
              <th scope="row">#{ticket.ticketId}</th>
              <td>{ticket.title}</td>
              <td><StatusBadge status={ticket.status} /></td>
              <td>{ticket.priority}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
