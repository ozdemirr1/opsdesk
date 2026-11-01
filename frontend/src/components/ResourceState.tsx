import type { ReactNode } from 'react';

/** Render only after a successful empty response, never in place of an error. */
export function EmptyState({ title, description, action }: {
  title: string; description?: string; action?: ReactNode;
}) {
  return <div className="empty-state">
    <p className="empty-state-title">{title}</p>
    {description && <p className="empty-state-description">{description}</p>}
    {action && <div className="empty-state-action">{action}</div>}
  </div>;
}

export function LoadingState({ children }: { children: ReactNode }) {
  return <p className="loading-state" role="status" aria-live="polite">
    <span className="loading-indicator" aria-hidden="true" />{children}
  </p>;
}
