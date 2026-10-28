import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { createOrganization, listOrganizations } from '../api/organizations';
import { useResource } from '../hooks/useResource';
import { navigate, ticketPath } from '../navigation';
import ResourceFeedback from './ResourceFeedback';

type Props = { token: string; onExpired: () => void };
export default function Organizations({ token, onExpired }: Props) {
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  return <section className="workspace-panel">
    <h2>Workspaces</h2>
    <p>Select an organization to view its tickets, or create your own.</p>
    <OrganizationPage key={`${offset}:${revision}`} token={token} onExpired={onExpired} offset={offset}
      onPage={setOffset} retry={() => setRevision(value => value + 1)} />
    <CreateOrganization token={token} onExpired={onExpired} />
  </section>;
}
function OrganizationPage({ token, onExpired, offset, onPage, retry }: Props & {
  offset: number; onPage: (offset: number) => void; retry: () => void;
}) {
  const load = useCallback((signal: AbortSignal) => listOrganizations(token, { offset, limit: 20 }, signal), [token, offset]);
  const result = useResource(load);
  if (!result) return <p role="status">Loading workspaces…</p>;
  if (!result.ok) return <ResourceFeedback result={result} onExpired={onExpired} retry={retry} />;
  return <>
    {result.data.total_count === 0 && <p>No workspaces yet. Create one below.</p>}
    <ul className="workspace-list">{result.data.items.map(({ organization, own_membership }) => <li key={organization.organization_id}>
      <div><strong>{organization.name}</strong><p>Your role: {own_membership.role}</p></div>
      {organization.is_active ? <a className="workspace-link" href={`#${ticketPath(organization.organization_id)}`}>Open {organization.name}</a> : <span>Suspended</span>}
    </li>)}</ul>
    {result.data.total_count > 0 && <div className="ticket-controls" aria-label="Workspace pagination">
      <button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 20))}>Previous workspaces</button>
      <span>{result.data.total_count} workspaces</span>
      <button disabled={offset + result.data.items.length >= result.data.total_count} onClick={() => onPage(offset + 20)}>Next workspaces</button>
    </div>}
  </>;
}
function CreateOrganization({ token, onExpired }: Props) {
  const [name, setName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (request.current) return;
    if (!name.trim()) { setError('Enter a workspace name.'); return; }
    const controller = new AbortController();
    request.current = controller;
    setPending(true); setError(null);
    try {
      const result = await createOrganization(token, { name }, controller.signal);
      if (controller.signal.aborted || request.current !== controller) return;
      if (result.ok) navigate(ticketPath(result.data.organization.organization_id));
      else if (result.kind === 'http' && result.status === 401) onExpired();
      else if (result.kind !== 'aborted') setError(result.kind === 'http' && result.status === 422
        ? 'Check the workspace name and try again.'
        : 'Creation could not be confirmed. Refresh the workspace list before trying again.');
    } catch {
      if (!controller.signal.aborted) setError('Creation could not be confirmed. Refresh the workspace list before trying again.');
    } finally {
      if (request.current === controller) { request.current = null; setPending(false); }
    }
  }
  return <form className="auth-form workspace-create" onSubmit={submit}>
    <h3>Create workspace</h3>
    <div className="form-group"><label htmlFor="organization-name">Workspace name</label>
      <input id="organization-name" value={name} onChange={event => setName(event.target.value)} required disabled={pending} /></div>
    <button className="submit-btn" disabled={pending}>{pending ? 'Creating…' : 'Create workspace'}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}
