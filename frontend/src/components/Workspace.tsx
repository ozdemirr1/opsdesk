import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { listOrganizations, type OrganizationContext } from '../api/organizations';
import { getTicket, listTickets, toTicketSummary, type TicketQuery } from '../api/tickets';
import type { ResourceResult } from '../api/resources';
import type { TicketStatus } from '../types/ticket';
import { useResource } from '../hooks/useResource';
import { navigate, ticketPath } from '../navigation';
import ResourceFeedback from './ResourceFeedback';
import TicketTable from './TicketTable';
import TicketDetail from './TicketDetail';
import Comments from './Comments';

type Props = { token: string; organizationId: number; ticketId?: number; onExpired: () => void };

/** Detail-only Organization responses omit role; resolve the actor's actual membership. */
async function loadContext(token: string, id: number, signal: AbortSignal): Promise<ResourceResult<OrganizationContext>> {
  let offset = 0;
  while (!signal.aborted) {
    const result = await listOrganizations(token, { offset, limit: 100 }, signal);
    if (!result.ok) return result;
    const match = result.data.items.find(item => item.organization.organization_id === id);
    if (match) return { ok: true, status: 200, data: match };
    offset += result.data.items.length;
    if (!result.data.items.length || offset >= result.data.total_count) break;
  }
  return signal.aborted
    ? { ok: false, kind: 'aborted', status: null, message: 'Request cancelled.' }
    : { ok: false, kind: 'http', status: 403, message: 'Workspace unavailable.' };
}
export default function Workspace(props: Props) {
  const [revision, setRevision] = useState(0);
  return <WorkspaceContent key={revision} {...props} retry={() => setRevision(value => value + 1)} />;
}
function WorkspaceContent({ token, organizationId, ticketId, onExpired, retry }: Props & { retry: () => void }) {
  const load = useCallback((signal: AbortSignal) => loadContext(token, organizationId, signal), [token, organizationId]);
  const result = useResource(load);
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  if (denied) return <section><h2>Workspace unavailable</h2><p role="alert">Your access has changed. Select a workspace again.</p><a href="#/organizations">Choose workspace</a></section>;
  if (!result) return <p role="status">Checking workspace membership…</p>;
  if (!result.ok) return <ResourceFeedback result={result} onExpired={onExpired} retry={retry} />;
  return <section className="workspace-panel">
    <div className="workspace-heading"><div><h2>{result.data.organization.name}</h2>
      <p>Your role: {result.data.own_membership.role}</p></div><a href="#/organizations">Change workspace</a></div>
    {!result.data.organization.is_active ? <p role="alert">This workspace is suspended. Tickets are unavailable.</p>
      : ticketId !== undefined ? <RemoteDetail key={ticketId} token={token} organizationId={organizationId} ticketId={ticketId} onExpired={onExpired} onDenied={onDenied} />
      : <RemoteDashboard token={token} organizationId={organizationId} onExpired={onExpired} onDenied={onDenied} />}
  </section>;
}
type ReadProps = Omit<Props, 'ticketId'> & { onDenied: () => void };
function ReadError({ result, onExpired, onDenied, retry }: {
  result: Exclude<ResourceResult<unknown>, { ok: true }>; onExpired: () => void; onDenied: () => void; retry: () => void;
}) {
  const denied = result.kind === 'http' && result.status === 403;
  useEffect(() => { if (denied) onDenied(); }, [denied, onDenied]);
  return <ResourceFeedback result={result} onExpired={onExpired} retry={retry} />;
}
function RemoteDetail({ token, organizationId, ticketId, onExpired, onDenied }: ReadProps & { ticketId: number }) {
  const [revision, setRevision] = useState(0);
  return <>
    <a href={`#${ticketPath(organizationId)}`}>Back to tickets</a>
    <DetailData key={revision} token={token} organizationId={organizationId} ticketId={ticketId}
      onExpired={onExpired} onDenied={onDenied} retry={() => setRevision(value => value + 1)} />
  </>;
}
function DetailData({ token, organizationId, ticketId, onExpired, onDenied, retry }: ReadProps & { ticketId: number; retry: () => void }) {
  const load = useCallback((signal: AbortSignal) => getTicket(token, organizationId, ticketId, signal), [token, organizationId, ticketId]);
  const result = useResource(load);
  if (!result) return <p role="status">Loading ticket…</p>;
  if (!result.ok) return <ReadError result={result} onExpired={onExpired} onDenied={onDenied} retry={retry} />;
  return <>
    <TicketDetail ticket={toTicketSummary(result.data)} isMock={false} onClose={() => navigate(ticketPath(organizationId))} />
    <Comments token={token} organizationId={organizationId} ticketId={ticketId}
      closed={result.data.status === 'closed'} onExpired={onExpired} onDenied={onDenied} refreshTicket={retry} />
  </>;
}
function RemoteDashboard(props: ReadProps) {
  const [draft, setDraft] = useState('');
  const [status, setStatus] = useState<TicketStatus | ''>('');
  const [query, setQuery] = useState<TicketQuery>({ limit: 20, offset: 0 });
  const [revision, setRevision] = useState(0);
  function submit(event: FormEvent) {
    event.preventDefault();
    setQuery({ limit: 20, offset: 0, ...(draft ? { q: draft } : {}), ...(status ? { status } : {}) });
  }
  return <>
    <h3>Tickets</h3>
    <p>Live workspace data. Search and filters apply to all tickets you can access.</p>
    <form className="ticket-controls" onSubmit={submit}>
      <div className="ticket-search"><label htmlFor="live-search">Search ticket titles</label>
        <input id="live-search" type="search" value={draft} onChange={event => setDraft(event.target.value)} /></div>
      <div className="ticket-status-filter"><label htmlFor="live-status">Status</label>
        <select id="live-status" value={status} onChange={event => {
          const value = event.target.value;
          if (value === '' || value === 'open' || value === 'in_progress' || value === 'resolved' || value === 'closed') setStatus(value);
        }}><option value="">All statuses</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option><option value="closed">Closed</option></select></div>
      <button type="submit">Apply filters</button>
      <button type="button" onClick={() => { setDraft(''); setStatus(''); setQuery({ limit: 20, offset: 0 }); }}>Clear filters</button>
    </form>
    <TicketPage key={revision} {...props} query={query} onPage={offset => setQuery(previous => ({ ...previous, offset }))}
      retry={() => setRevision(value => value + 1)} />
  </>;
}
function TicketPage({ token, organizationId, onExpired, onDenied, query, onPage, retry }: ReadProps & {
  query: TicketQuery; onPage: (offset: number) => void; retry: () => void;
}) {
  const load = useCallback((signal: AbortSignal) => listTickets(token, organizationId, query, signal), [token, organizationId, query]);
  const result = useResource(load);
  if (!result) return <p role="status">Loading tickets…</p>;
  if (!result.ok) return <ReadError result={result} onExpired={onExpired} onDenied={onDenied} retry={retry} />;
  const { items, total_count, offset, limit } = result.data;
  return <>
    <p className="ticket-result-count" role="status">{total_count} matching tickets</p>
    {items.length ? <TicketTable tickets={items.map(toTicketSummary)} onSelectTicket={id => navigate(ticketPath(organizationId, id))} />
      : <p>{offset > 0 ? 'No tickets on this page.' : query.q || query.status ? 'No matching tickets.' : 'No tickets yet.'}</p>}
    <div className="ticket-controls" aria-label="Ticket pagination">
      <button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}>Previous page</button>
      <button disabled={offset + items.length >= total_count} onClick={() => onPage(offset + limit)}>Next page</button>
    </div>
  </>;
}
