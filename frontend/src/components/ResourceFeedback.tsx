import { useEffect } from 'react';
import type { ResourceResult } from '../api/resources';

type Props = { result: Exclude<ResourceResult<unknown>, { ok: true }>; onExpired: () => void; retry: () => void };
export default function ResourceFeedback({ result, onExpired, retry }: Props) {
  const expired = result.kind === 'http' && result.status === 401;
  useEffect(() => { if (expired) onExpired(); }, [expired, onExpired]);
  if (expired) return <p role="status">Your session has expired.</p>;
  if (result.kind === 'aborted') return null;
  const denied = result.kind === 'http' && result.status === 403;
  const missing = result.kind === 'http' && result.status === 404;
  return <div className="resource-feedback">
    <p role="alert">{denied ? 'Access is unavailable. Choose a workspace again to refresh your membership.' : missing ? 'This record is unavailable.' : 'Unable to load data. Please try again.'}</p>
    {!denied && !missing && <button type="button" onClick={retry}>Retry</button>}
    {(denied || missing) && <a href="#/organizations">Choose workspace</a>}
  </div>;
}
