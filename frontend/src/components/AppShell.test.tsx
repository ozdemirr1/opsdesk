import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppShell from './AppShell';

test('keyboard skip link focuses content without changing the protected hash route', async () => {
  window.history.replaceState(null, '', '#/organizations/10/tickets/1');
  const user = userEvent.setup();
  render(<AppShell email="demo@example.com" navigation={<nav aria-label="Screens"><button>Workspaces</button></nav>}>
    <h2>Ticket details</h2><button>Save priority</button>
  </AppShell>);
  await user.tab();
  expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(screen.getByRole('main')).toHaveFocus();
  expect(window.location.hash).toBe('#/organizations/10/tickets/1');
  await user.tab();
  expect(screen.getByRole('button', { name: 'Save priority' })).toHaveFocus();
});

test('sign-out replaces private identity and navigation without leaving duplicate landmarks', () => {
  const view = render(<AppShell email="demo@example.com" navigation={<nav aria-label="Screens"><button>Account</button></nav>}><h2>Workspaces</h2></AppShell>);
  view.rerender(<AppShell navigation={<nav aria-label="Screens"><button>Login</button></nav>}><h2>Login</h2></AppShell>);
  expect(screen.queryByText('demo@example.com')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Account' })).not.toBeInTheDocument();
  expect(screen.getAllByRole('main')).toHaveLength(1);
  expect(screen.getAllByRole('navigation')).toHaveLength(1);
});
