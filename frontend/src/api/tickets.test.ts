import { expect, test } from 'vitest';
import { toTicketSummary, type TicketResponse } from './tickets';

const response: TicketResponse = {
  ticket_id: 101,
  organization_id: 10,
  requester_membership_id: 20,
  creator_membership_id: 20,
  assignee_membership_id: null,
  title: 'Cannot access workspace',
  description: 'Sign-in succeeds, but the workspace does not open.',
  status: 'open',
  priority: 'high',
  created_at: '2026-10-24T09:00:00Z',
  updated_at: '2026-10-24T09:00:00Z',
};

test('projects an API ticket into only the table and detail fields', () => {
  expect(toTicketSummary(response)).toEqual({
    ticketId: 101,
    title: 'Cannot access workspace',
    description: 'Sign-in succeeds, but the workspace does not open.',
    status: 'open',
    priority: 'high',
  });
});

test.each(['', 'First line.\nSecond line: café access issue.'])(
  'preserves description content: %j',
  (description) => {
    const summary = toTicketSummary({ ...response, description });
    expect(summary.description).toBe(description);
  },
);

test('does not change the source and returns an independent display object', () => {
  const source = Object.freeze({
    ...response,
    assignee_membership_id: 30,
    status: 'in_progress' as const,
    priority: 'urgent' as const,
  });
  const before = { ...source };

  const first = toTicketSummary(source);
  const second = toTicketSummary(source);

  expect(first).toMatchObject({ status: 'in_progress', priority: 'urgent' });
  expect(first).not.toBe(second);
  first.title = 'Local display edit';
  first.description = 'Local description edit';

  expect(source).toEqual(before);
  expect(second.title).toBe(source.title);
  expect(second.description).toBe(source.description);
});
