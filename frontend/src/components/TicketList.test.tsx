import { expect, test } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import TicketList from './TicketList';
import type { TicketSummary } from '../types/ticket';

const testTickets: TicketSummary[] = [
  {
    ticketId: 501,
    title: 'Test ticket 1',
    status: 'open',
    priority: 'urgent',
  },
  {
    ticketId: 502,
    title: 'Test ticket 2',
    status: 'resolved',
    priority: 'low',
  },
];

test('renders correctly with an empty list', () => {
  render(<TicketList tickets={[]} />);

  expect(screen.getByText('No tickets yet.')).toBeInTheDocument();
  expect(screen.queryByRole('list')).not.toBeInTheDocument();
  expect(screen.queryAllByRole('listitem')).toHaveLength(0);
});

test('renders correctly with a populated list', () => {
  render(<TicketList tickets={testTickets} />);

  const list = screen.getByRole('list', { name: 'Ticket list' });
  expect(list).toBeInTheDocument();

  const rows = within(list).getAllByRole('listitem');
  expect(rows).toHaveLength(2);

  // Check first row
  const firstRow = within(rows[0]);
  expect(firstRow.getByRole('heading', { level: 3, name: 'Test ticket 1' })).toBeInTheDocument();
  expect(firstRow.getByText('ID: #501')).toBeInTheDocument();
  expect(firstRow.getByText('Status: open')).toBeInTheDocument();
  expect(firstRow.getByText('Priority: urgent')).toBeInTheDocument();

  // Check second row
  const secondRow = within(rows[1]);
  expect(secondRow.getByRole('heading', { level: 3, name: 'Test ticket 2' })).toBeInTheDocument();
  expect(secondRow.getByText('ID: #502')).toBeInTheDocument();
  expect(secondRow.getByText('Status: resolved')).toBeInTheDocument();
  expect(secondRow.getByText('Priority: low')).toBeInTheDocument();
});
