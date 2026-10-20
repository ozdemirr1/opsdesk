import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBadge from './StatusBadge';
import type { TicketStatus } from '../types/ticket';

const cases: [TicketStatus, string][] = [
  ['open', 'Open'],
  ['in_progress', 'In progress'],
  ['resolved', 'Resolved'],
  ['closed', 'Closed'],
];

test.each(cases)('shows a readable label for %s without relying on color', (status, label) => {
  render(<StatusBadge status={status} />);
  expect(screen.getByText(label)).toBeVisible();
});

test('updates the label when the status prop changes', () => {
  const { rerender } = render(<StatusBadge status="open" />);
  rerender(<StatusBadge status="closed" />);
  expect(screen.getByText('Closed')).toBeVisible();
  expect(screen.queryByText('Open')).not.toBeInTheDocument();
});
