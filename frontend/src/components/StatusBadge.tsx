import type { TicketStatus } from '../types/ticket';

type StatusBadgeProps = {
  status: TicketStatus;
};

const statusLabels: Record<TicketStatus, string> = {
  open: 'Open',
  in_progress: 'In progress',
  resolved: 'Resolved',
  closed: 'Closed',
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${status}`}>
      {statusLabels[status]}
    </span>
  );
}
