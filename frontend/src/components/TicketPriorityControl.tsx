import { useEffect, useRef, useState, type FormEvent } from 'react';
import { changeTicketPriority, type TicketResponse } from '../api/tickets';
import type { OrganizationRole } from '../api/organizations';
import type { TicketPriority } from '../types/ticket';

type Props = {
  token: string; ticket: TicketResponse; role: OrganizationRole;
  onUpdated: (ticket: TicketResponse) => void;
  onExpired: () => void; onDenied: () => void; onMissing: () => void;
  refreshTicket: () => void;
};
export default function TicketPriorityControl(props: Props) {
  if (!['agent', 'admin', 'owner'].includes(props.role)) return null;
  if (!['open', 'in_progress'].includes(props.ticket.status)) {
    return <p>Priority cannot be changed on resolved or closed tickets.</p>;
  }
  const { token, ticket, role } = props;
  return <PriorityForm key={`${token}:${ticket.organization_id}:${ticket.ticket_id}:${role}:${ticket.status}:${ticket.priority}`} {...props} />;
}
function PriorityForm({ token, ticket, onUpdated, onExpired, onDenied, onMissing, refreshTicket }: Props) {
  const [priority, setPriority] = useState<TicketPriority>(ticket.priority);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (request.current || needsRefresh) return;
    const controller = new AbortController(); request.current = controller;
    setPending(true); setError(null);
    try {
      const result = await changeTicketPriority(token, ticket.organization_id, ticket.ticket_id, priority, controller.signal);
      if (controller.signal.aborted || request.current !== controller) return;
      if (result.ok) onUpdated(result.data);
      else if (result.kind === 'http' && result.status === 401) onExpired();
      else if (result.kind === 'http' && result.status === 403) onDenied();
      else if (result.kind === 'http' && result.status === 404) onMissing();
      else if (result.kind === 'http' && result.status === 422) setError('Select a valid priority and try again.');
      else if (result.kind !== 'aborted') {
        setNeedsRefresh(true);
        setError(result.kind === 'http' && result.status === 409
          ? 'The ticket state has changed. Refresh the ticket before updating its priority.'
          : 'The change could not be confirmed. Refresh the ticket to check its priority before trying again.');
      }
    } catch {
      if (!controller.signal.aborted && request.current === controller) {
        setNeedsRefresh(true);
        setError('The change could not be confirmed. Refresh the ticket to check its priority before trying again.');
      }
    } finally {
      if (request.current === controller) { request.current = null; setPending(false); }
    }
  }
  return <form className="ticket-controls priority-control" aria-label="Ticket priority" onSubmit={submit}>
    <div className="ticket-status-filter"><label htmlFor="ticket-priority">Priority</label>
      <select id="ticket-priority" value={priority} disabled={pending || needsRefresh} onChange={event => {
        const value = event.target.value;
        if (value === 'low' || value === 'medium' || value === 'high' || value === 'urgent') setPriority(value);
      }}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select>
    </div>
    <button type="submit" disabled={pending || needsRefresh}>{pending ? 'Saving priority…' : 'Save priority'}</button>
    {error && <p role="alert">{error}</p>}
    {needsRefresh && <button type="button" onClick={refreshTicket}>Refresh ticket</button>}
  </form>;
}
