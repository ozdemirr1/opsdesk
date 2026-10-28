import type { TicketSummary } from '../types/ticket';
import StatusBadge from './StatusBadge';

type TicketDetailProps = {
  ticket: TicketSummary;
  onClose: () => void;
  isMock?: boolean;
};

export default function TicketDetail({ ticket, onClose, isMock = true }: TicketDetailProps) {
  return (
    <section className="ticket-detail" aria-label={isMock ? 'Mock ticket details' : 'Ticket details'}>
      <div className="ticket-detail-header">
        <div>
          <p className="ticket-detail-eyebrow">{isMock ? 'MOCK TICKET' : 'TICKET'} · #{ticket.ticketId}</p>
          <h3>{ticket.title}</h3>
        </div>
        <button type="button" className="ticket-close-button" onClick={onClose} autoFocus>
          Close details
        </button>
      </div>

      <dl className="ticket-detail-meta">
        <div>
          <dt>ID</dt>
          <dd>#{ticket.ticketId}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd><StatusBadge status={ticket.status} /></dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{ticket.priority}</dd>
        </div>
      </dl>
      <div className="ticket-detail-description">
        <h4>Description</h4>
        <p>{ticket.description ?? 'No description provided.'}</p>
      </div>
    </section>
  );
}
