import { expect, test } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TicketDashboard from './TicketDashboard';
import type { TicketSummary } from '../types/ticket';

const tickets: TicketSummary[] = [
  { ticketId: 501, title: 'Cannot access workspace', status: 'open', priority: 'high' },
  { ticketId: 502, title: 'EMAIL notifications delayed', status: 'in_progress', priority: 'medium' },
  { ticketId: 503, title: 'Update support contact', status: 'resolved', priority: 'low' },
];

function displayedIds() {
  const table = screen.getByRole('table', { name: 'Ticket list' });
  return within(table).getAllByRole('rowheader').map((cell) => cell.textContent);
}

test('starts with an empty search and all supplied tickets', () => {
  render(<TicketDashboard tickets={tickets} />);
  expect(screen.getByRole('searchbox', { name: 'Search tickets' })).toHaveValue('');
  expect(displayedIds()).toEqual(['#501', '#502', '#503']);
  expect(screen.queryByText('No matching tickets.')).not.toBeInTheDocument();
});

test.each(['mail', '  eMaIl  '])('searches titles with %j and preserves the entered text', async (query) => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={tickets} />);
  const input = screen.getByRole('searchbox', { name: 'Search tickets' });
  await user.type(input, query);
  expect(input).toHaveValue(query);
  expect(displayedIds()).toEqual(['#502']);

  await user.clear(input);
  expect(displayedIds()).toEqual(['#501', '#502', '#503']);
  await user.type(input, '   ');
  expect(displayedIds()).toEqual(['#501', '#502', '#503']);
});

test('shows no matches for text outside titles and recovers when cleared', async () => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={tickets} />);
  const input = screen.getByRole('searchbox', { name: 'Search tickets' });
  await user.type(input, 'high');
  expect(screen.getByText('No matching tickets.')).toBeVisible();
  expect(screen.queryByText('No tickets yet.')).not.toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();

  await user.clear(input);
  expect(displayedIds()).toEqual(['#501', '#502', '#503']);
  expect(screen.queryByText('No matching tickets.')).not.toBeInTheDocument();
});

test('keeps the source-empty message even when search text is entered', async () => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={[]} />);
  expect(screen.getByText('No tickets yet.')).toBeVisible();
  await user.type(screen.getByRole('searchbox', { name: 'Search tickets' }), 'email');
  expect(screen.getByText('No tickets yet.')).toBeVisible();
  expect(screen.queryByText('No matching tickets.')).not.toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

test('applies the current search to changed ticket props', async () => {
  const user = userEvent.setup();
  const { rerender } = render(<TicketDashboard tickets={tickets} />);
  await user.type(screen.getByRole('searchbox', { name: 'Search tickets' }), 'email');
  expect(displayedIds()).toEqual(['#502']);

  rerender(<TicketDashboard tickets={[
    { ticketId: 504, title: 'Email delivery restored', status: 'closed', priority: 'low' },
    tickets[0],
  ]} />);
  expect(screen.getByRole('searchbox', { name: 'Search tickets' })).toHaveValue('email');
  expect(displayedIds()).toEqual(['#504']);
  expect(screen.queryByText('EMAIL notifications delayed')).not.toBeInTheDocument();
});
