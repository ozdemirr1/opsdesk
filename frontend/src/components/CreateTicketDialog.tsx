import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createTicket, validateTicketInput, type TicketResponse } from '../api/tickets';
import type { TicketPriority } from '../types/ticket';

type Props = {
  token: string;
  organizationId: number;
  onClose: () => void;
  onCreated: (ticket: TicketResponse) => void;
  onExpired: () => void;
  onDenied: () => void;
  onReviewList: () => void;
};

export default function CreateTicketDialog({ token, organizationId, onClose, onCreated, onExpired, onDenied, onReviewList }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleInput = useRef<HTMLInputElement>(null);
  const descriptionInput = useRef<HTMLTextAreaElement>(null);
  const request = useRef<AbortController | null>(null);
  const deadline = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('medium');
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<{ title?: string; description?: string }>({});

  useEffect(() => {
    const element = dialog.current!;
    const opener = document.activeElement;
    element.showModal();
    titleInput.current?.focus();
    return () => {
      request.current?.abort();
      request.current = null;
      if (deadline.current !== null) clearTimeout(deadline.current);
      element.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);

  function markUncertain() {
    setUncertain(true);
    setError('Creation could not be confirmed. The ticket may have been saved. Check the ticket list before creating another.');
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (request.current || uncertain) return;
    const input = { title, description, priority };
    const errors = validateTicketInput(input);
    setFields(errors);
    if (errors.title || errors.description) {
      (errors.title ? titleInput.current : descriptionInput.current)?.focus();
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError(null);
    // Aborting the client cannot undo a server write. A timeout is uncertain.
    deadline.current = setTimeout(() => {
      if (request.current !== controller) return;
      controller.abort();
      request.current = null;
      setPending(false);
      markUncertain();
    }, 30_000);
    try {
      const result = await createTicket(token, organizationId, input, controller.signal);
      if (controller.signal.aborted || request.current !== controller) return;
      if (result.ok) onCreated(result.data);
      else if (result.kind === 'http' && result.status === 401) onExpired();
      else if (result.kind === 'http' && (result.status === 403 || result.status === 404)) onDenied();
      else if (result.kind === 'http' && result.status === 422) setError('Check the title, description and priority, then try again.');
      else if (result.kind === 'invalid_request') setError('Check the form values and try again.');
      else if (result.kind !== 'aborted') markUncertain();
    } catch {
      if (!controller.signal.aborted && request.current === controller) markUncertain();
    } finally {
      if (request.current === controller) {
        request.current = null;
        if (deadline.current !== null) clearTimeout(deadline.current);
        deadline.current = null;
        setPending(false);
      }
    }
  }

  return <dialog ref={dialog} className="create-ticket-dialog" aria-labelledby="create-ticket-heading"
    aria-describedby="create-ticket-help" onCancel={event => { event.preventDefault(); if (!request.current) onClose(); }}>
    <div className="modal-heading"><h2 id="create-ticket-heading">Create ticket</h2>
      <button type="button" onClick={onClose} disabled={pending} aria-label="Close create ticket">Close</button></div>
    <p id="create-ticket-help">Describe the issue for this workspace. You will be recorded as the requester.</p>
    <form className="create-ticket-form" onSubmit={submit} noValidate aria-busy={pending}>
      {(fields.title || fields.description) && <p role="alert">Check the highlighted fields before creating the ticket.</p>}
      <div className="form-group"><label htmlFor="new-ticket-title">Title</label>
        <input ref={titleInput} id="new-ticket-title" value={title} required disabled={pending || uncertain}
          aria-invalid={Boolean(fields.title)} aria-describedby="ticket-title-help" onChange={event => setTitle(event.target.value)} />
        <p id="ticket-title-help" className={fields.title ? 'field-error' : 'field-help'}>{fields.title ?? '1–255 characters, on a single line.'}</p></div>
      <div className="form-group"><label htmlFor="new-ticket-description">Description</label>
        <textarea ref={descriptionInput} id="new-ticket-description" value={description} required disabled={pending || uncertain}
          rows={5} aria-invalid={Boolean(fields.description)} aria-describedby="ticket-description-help" onChange={event => setDescription(event.target.value)} />
        <p id="ticket-description-help" className={fields.description ? 'field-error' : 'field-help'}>{fields.description ?? '1–10,000 characters. Include the steps and what you expected.'}</p></div>
      <div className="form-group"><label htmlFor="new-ticket-priority">Priority</label>
        <select id="new-ticket-priority" value={priority} disabled={pending || uncertain} onChange={event => {
          const value = event.target.value;
          if (value === 'low' || value === 'medium' || value === 'high' || value === 'urgent') setPriority(value);
        }}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select></div>
      {error && <p role="alert">{error}</p>}
      {pending && <p role="status">Creating ticket… Please wait for the result.</p>}
      <div className="modal-actions">
        <button type="button" disabled={pending} onClick={onClose}>Cancel</button>
        {uncertain ? <button type="button" className="submit-btn" onClick={onReviewList}>Check ticket list</button>
          : <button className="submit-btn" type="submit" disabled={pending}>{pending ? 'Creating…' : 'Create ticket'}</button>}
      </div>
    </form>
  </dialog>;
}
