import { expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

test('renders Tickets heading and list initially, no Login/Register headings, and Tickets button is selected', () => {
  render(<App />)

  // Check headings
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Register', level: 2 })).not.toBeInTheDocument()

  // Check initial list presence
  expect(screen.getByRole('list', { name: 'Ticket list' })).toBeInTheDocument()

  // Check the selected button
  expect(screen.getByRole('button', { name: 'Tickets' })).toHaveAttribute('aria-pressed', 'true')
})

test('navigates to Login screen and returns to Tickets screen showing the list again', async () => {
  const user = userEvent.setup()
  render(<App />)

  const loginBtn = screen.getByRole('button', { name: 'Login' })
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' })

  // Click the Login button
  await user.click(loginBtn)

  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Ticket list' })).not.toBeInTheDocument()

  // Verify form fields are rendered on the Login screen
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument()

  expect(loginBtn).toHaveAttribute('aria-pressed', 'true')

  // Click the Tickets button again
  await user.click(ticketsBtn)

  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Ticket list' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument()

  // Verify form fields are removed from the DOM
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()

  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'true')
})

test('shows only Register heading when navigated to Register, and form fields reset on screen return', async () => {
  const user = userEvent.setup();
  render(<App />);

  const registerBtn = screen.getByRole('button', { name: 'Register' });
  const loginBtn = screen.getByRole('button', { name: 'Login' });
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' });

  // Click the Register button
  await user.click(registerBtn);

  expect(screen.getByRole('heading', { name: 'Register', level: 2 })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument();
  expect(screen.queryByRole('list', { name: 'Ticket list' })).not.toBeInTheDocument();

  // Form fields should be visible
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  expect(emailInput).toBeInTheDocument();
  expect(passwordInput).toBeInTheDocument();
  expect(confirmPasswordInput).toBeInTheDocument();

  // Check button states
  expect(registerBtn).toHaveAttribute('aria-pressed', 'true');
  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'false');
  expect(loginBtn).toHaveAttribute('aria-pressed', 'false');

  // Type mismatched data into fields and submit
  await user.type(emailInput, 'draft@example.com');
  await user.type(passwordInput, 'draftPassword1');
  await user.type(confirmPasswordInput, 'differentPassword2');
  await user.click(submitBtn);

  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');

  // Switch to Tickets screen
  await user.click(ticketsBtn);

  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument();
  expect(screen.getByRole('list', { name: 'Ticket list' })).toBeInTheDocument();
  expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^Password/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^Confirm password/i)).not.toBeInTheDocument();

  // Return to Register screen and verify fields and feedback are reset
  await user.click(registerBtn);

  expect(screen.getByRole('heading', { name: 'Register', level: 2 })).toBeInTheDocument();
  expect(screen.getByLabelText(/email/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Password/i)).toHaveValue('');
  expect(screen.getByLabelText(/^Confirm password/i)).toHaveValue('');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
