import { useEffect, useRef } from 'react';
import type { TicketSummary } from '../types/ticket';
import StatusBadge from './StatusBadge';

type TicketTableProps = {
  tickets: TicketSummary[];
  onSelectTicket?: (ticketId: number) => void;
  focusTicketId?: number | null;
  selectedTicketId?: number | null;
};

export default function TicketTable({
  tickets,
  onSelectTicket,
  focusTicketId,
  selectedTicketId,
}: TicketTableProps) {
  const titleButtons = useRef(new Map<number, HTMLButtonElement>());

  useEffect(() => {
    if (focusTicketId !== null && focusTicketId !== undefined) {
      titleButtons.current.get(focusTicketId)?.focus();
    }
  }, [focusTicketId]);

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
            <tr key={ticket.ticketId} data-selected={selectedTicketId === ticket.ticketId}>
              <th scope="row">#{ticket.ticketId}</th>
              <td>
                {onSelectTicket ? (
                  <button
                    type="button"
                    className="ticket-title-button"
                    onClick={() => onSelectTicket(ticket.ticketId)}
                    aria-label={`View ticket #${ticket.ticketId}: ${ticket.title}`}
                    aria-expanded={selectedTicketId === ticket.ticketId}
                    ref={(element) => {
                      if (element) {
                        titleButtons.current.set(ticket.ticketId, element);
                      } else {
                        titleButtons.current.delete(ticket.ticketId);
                      }
                    }}
                  >
                    {ticket.title}
                  </button>
                ) : (
                  ticket.title
                )}
              </td>
              <td><StatusBadge status={ticket.status} /></td>
              <td>{ticket.priority}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
