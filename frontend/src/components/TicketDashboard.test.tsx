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
  expect(screen.getByRole('combobox', { name: 'Status' })).toHaveValue('all');
  expect(screen.getByText('Showing 3 of 3 tickets')).toBeVisible();
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

test.each([
  ['open', '#501'],
  ['in_progress', '#502'],
  ['resolved', '#503'],
  ['closed', null],
])('filters status %s to the expected rows', async (status, expectedId) => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={tickets} />);
  await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), status);

  expect(screen.getByRole('combobox', { name: 'Status' })).toHaveValue(status);
  if (expectedId === null) {
    expect(screen.getByText('No matching tickets.')).toBeVisible();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 0 of 3 tickets')).toBeVisible();
  } else {
    expect(displayedIds()).toEqual([expectedId]);
    expect(screen.getByText('Showing 1 of 3 tickets')).toBeVisible();
  }
});

test('combines title and status, then clears both filters from a no-match state', async () => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={tickets} />);
  const search = screen.getByRole('searchbox', { name: 'Search tickets' });
  const status = screen.getByRole('combobox', { name: 'Status' });

  await user.type(search, '  email  ');
  await user.selectOptions(status, 'in_progress');
  expect(displayedIds()).toEqual(['#502']);
  expect(screen.getByText('Showing 1 of 3 tickets')).toBeVisible();

  await user.selectOptions(status, 'open');
  expect(screen.getByText('No matching tickets.')).toBeVisible();
  expect(screen.getByText('Showing 0 of 3 tickets')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Clear filters' }));
  expect(search).toHaveValue('');
  expect(status).toHaveValue('all');
  expect(displayedIds()).toEqual(['#501', '#502', '#503']);
  expect(screen.getByText('Showing 3 of 3 tickets')).toBeVisible();
});

test('keeps the empty-source message when a status is selected', async () => {
  const user = userEvent.setup();
  render(<TicketDashboard tickets={[]} />);
  await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'closed');
  expect(screen.getByText('No tickets yet.')).toBeVisible();
  expect(screen.queryByText('No matching tickets.')).not.toBeInTheDocument();
  expect(screen.getByText('Showing 0 of 0 tickets')).toBeVisible();
});
