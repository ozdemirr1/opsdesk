import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { listComments, postComment, validCommentContent } from '../api/comments';
import { useResource } from '../hooks/useResource';
import ResourceFeedback from './ResourceFeedback';

type Props = {
  token: string; organizationId: number; ticketId: number; closed: boolean;
  onExpired: () => void; onDenied: () => void; refreshTicket: () => void;
};
export default function Comments(props: Props) {
  return <CommentThread key={`${props.token}:${props.organizationId}:${props.ticketId}`} {...props} />;
}
function CommentThread(props: Props) {
  const { token, organizationId, ticketId, closed, onExpired, onDenied, refreshTicket } = props;
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const load = useCallback((signal: AbortSignal) => {
    void revision;
    return listComments(token, organizationId, ticketId, { limit: 20, offset }, signal);
  }, [token, organizationId, ticketId, offset, revision]);
  const result = useResource(load);
  useEffect(() => {
    if (result && !result.ok && result.kind === 'http') {
      if (result.status === 403) onDenied();
    }
  }, [result, onDenied]);
  const refresh = () => setRevision(value => value + 1);
  const restricted = result && !result.ok && result.kind === 'http' && [401, 403, 404].includes(result.status ?? 0);
  if (restricted) return <>
    <ResourceFeedback result={result} onExpired={onExpired} retry={refresh} />
    {result.status === 404 && <button type="button" onClick={refreshTicket}>Refresh ticket</button>}
  </>;
  return <section className="comment-thread" aria-label="Ticket comments">
    <div className="comment-heading"><h3>Comments</h3>
      <button type="button" onClick={refresh}>Refresh comments</button></div>
    {!result ? <p role="status">Loading comments…</p>
      : !result.ok ? <ResourceFeedback result={result} onExpired={onExpired} retry={refresh} />
      : <>
        <p>{result.data.total_count} comments</p>
        {result.data.items.length === 0 ? <p>{offset ? 'No comments on this page.' : 'No comments yet. Start the conversation.'}</p>
          : <ol className="comment-list">{result.data.items.map(comment => <li key={comment.comment_id}>
            <div className="comment-meta"><strong>Member #{comment.author_membership_id}</strong>
              <time dateTime={comment.created_at}>{new Date(comment.created_at).toLocaleString()}</time></div>
            <p>{comment.content}</p>
          </li>)}</ol>}
        <nav className="ticket-controls" aria-label="Comment pagination">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous comments</button>
          <button type="button" disabled={offset + result.data.items.length >= result.data.total_count} onClick={() => setOffset(offset + 20)}>Next comments</button>
        </nav>
      </>}
    {closed ? <p>This ticket is closed. Comments are read-only.</p>
      : <CommentForm {...props} disabled={!result?.ok} onCreated={() => {
        if (result?.ok) setOffset(Math.floor(result.data.total_count / 20) * 20);
        refresh();
      }} />}
  </section>;
}
function CommentForm({ token, organizationId, ticketId, onExpired, onDenied, refreshTicket, disabled, onCreated }: Props & {
  disabled: boolean; onCreated: () => void;
}) {
  const [content, setContent] = useState('');
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (request.current || disabled || conflict) return;
    if (!validCommentContent(content)) { setError('Enter a comment of 1–10,000 characters without unsupported control characters.'); return; }
    const controller = new AbortController();
    request.current = controller;
    setPending(true); setError(null); setSuccess(false);
    try {
      const result = await postComment(token, organizationId, ticketId, content, controller.signal);
      if (controller.signal.aborted || request.current !== controller) return;
      if (result.ok) { setContent(''); setSuccess(true); onCreated(); }
      else if (result.kind === 'http' && result.status === 401) onExpired();
      else if (result.kind === 'http' && result.status === 403) onDenied();
      else if (result.kind === 'http' && result.status === 404) refreshTicket();
      else if (result.kind === 'http' && result.status === 409) {
        setConflict(true); setError('This ticket no longer accepts comments. Refresh the ticket to see its current state.');
      } else if (result.kind === 'http' && result.status === 422) setError('Check the comment content and try again.');
      else if (result.kind !== 'aborted') setError('Posting could not be confirmed. Refresh and check the comments before sending again.');
    } catch {
      if (!controller.signal.aborted) setError('Posting could not be confirmed. Refresh and check the comments before sending again.');
    } finally {
      if (request.current === controller) { request.current = null; setPending(false); }
    }
  }
  return <form className="comment-form" onSubmit={submit}>
    <label htmlFor="comment-content">Add a comment</label>
    <textarea id="comment-content" rows={4} value={content} disabled={pending || conflict || disabled}
      aria-describedby="comment-help" onChange={event => { setContent(event.target.value); setSuccess(false); }} />
    <p id="comment-help">Up to 10,000 characters. Comments cannot be edited or deleted.</p>
    <button type="submit" disabled={pending || conflict || disabled}>{pending ? 'Posting…' : 'Post comment'}</button>
    {error && <p role="alert">{error}</p>}
    {conflict && <button type="button" onClick={refreshTicket}>Refresh ticket</button>}
    {success && <p role="status">Comment posted.</p>}
  </form>;
}
