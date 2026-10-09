import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginForm from './LoginForm';

test('allows typing in fields and updates their values', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);

  await user.type(emailInput, 'test@example.com');
  await user.type(passwordInput, 'mysecretpassword');

  expect(emailInput).toHaveValue('test@example.com');
  expect(passwordInput).toHaveValue('mysecretpassword');
});

test('shows error when submitting with empty email', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });
  await user.click(submitBtn);

  const errorMessage = screen.getByRole('alert');
  expect(errorMessage).toHaveTextContent('Email is required.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when submitting with valid email but empty password', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });

  await user.type(emailInput, 'valid@example.com');
  await user.click(submitBtn);

  const errorMessage = screen.getByRole('alert');
  expect(errorMessage).toHaveTextContent('Password is required.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when submitting with invalid email format', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });

  await user.type(emailInput, 'not-an-email');
  await user.click(submitBtn);

  const errorMessage = screen.getByRole('alert');
  expect(errorMessage).toHaveTextContent('Enter a valid email address.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows success status on valid submission, clears password, keeps email', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });

  await user.type(emailInput, 'learner@example.com');
  await user.type(passwordInput, 'x'.repeat(16));
  await user.click(submitBtn);

  const successMessage = screen.getByRole('status');
  expect(successMessage).toHaveTextContent('Demo only: no sign-in request was sent.');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();

  // Password should be cleared, email should remain
  expect(passwordInput).toHaveValue('');
  expect(emailInput).toHaveValue('learner@example.com');
});

test('clears error message when email is edited', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });

  // Trigger an error first
  await user.click(submitBtn);
  expect(screen.getByRole('alert')).toBeInTheDocument();

  // Type in email input to clear the error
  await user.type(emailInput, 'a');

  // The alert should be removed from the DOM
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('clears success message when password is edited', async () => {
  const user = userEvent.setup();
  render(<LoginForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  const submitBtn = screen.getByRole('button', { name: 'Continue demo' });

  // Submit valid demo form
  await user.type(emailInput, 'learner@example.com');
  await user.type(passwordInput, 'x'.repeat(16));
  await user.click(submitBtn);

  // Status message should be visible
  expect(screen.getByRole('status')).toBeInTheDocument();

  // Edit the emptied password input
  await user.type(passwordInput, 'newpassword123');

  // Both status and alert messages should be removed
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
