import { expect, test } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import TicketTable from './TicketTable';
import type { TicketSummary } from '../types/ticket';

const testTickets: TicketSummary[] = [
  { ticketId: 501, title: 'Test ticket 1', status: 'open', priority: 'urgent' },
  { ticketId: 502, title: 'Test ticket 2', status: 'resolved', priority: 'low' },
];

test('shows an empty state without an empty table', () => {
  render(<TicketTable tickets={[]} />);
  expect(screen.getByText('No tickets yet.')).toBeVisible();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

test('renders a named table with column headers and correctly associated ticket fields', () => {
  render(<TicketTable tickets={testTickets} />);
  const table = screen.getByRole('table', { name: 'Ticket list' });
  expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent))
    .toEqual(['ID', 'Title', 'Status', 'Priority']);
  const rows = within(table).getAllByRole('row');
  expect(rows).toHaveLength(3);
  expect(within(rows[1]).getByRole('rowheader', { name: '#501' })).toBeVisible();
  expect(within(rows[1]).getAllByRole('cell').map((cell) => cell.textContent))
    .toEqual(['Test ticket 1', 'Open', 'urgent']);
  expect(within(rows[2]).getByRole('rowheader', { name: '#502' })).toBeVisible();
  expect(within(rows[2]).getAllByRole('cell').map((cell) => cell.textContent))
    .toEqual(['Test ticket 2', 'Resolved', 'low']);
  expect(screen.queryByText('No tickets yet.')).not.toBeInTheDocument();
});

test('reflects changed props and returns to the empty state', () => {
  const { rerender } = render(<TicketTable tickets={testTickets} />);
  rerender(<TicketTable tickets={[{ ...testTickets[1], status: 'closed' }]} />);
  const table = screen.getByRole('table', { name: 'Ticket list' });
  expect(within(table).getAllByRole('row')).toHaveLength(2);
  expect(within(table).getByText('Closed')).toBeVisible();
  expect(within(table).queryByText('Test ticket 1')).not.toBeInTheDocument();
  rerender(<TicketTable tickets={[]} />);
  expect(screen.getByText('No tickets yet.')).toBeVisible();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});
