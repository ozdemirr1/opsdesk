import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RegisterForm from './RegisterForm';

test('allows typing in all three fields and updates values', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);

  await user.type(emailInput, 'user@example.com');
  await user.type(passwordInput, 'secret123');
  await user.type(confirmPasswordInput, 'secret123');

  expect(emailInput).toHaveValue('user@example.com');
  expect(passwordInput).toHaveValue('secret123');
  expect(confirmPasswordInput).toHaveValue('secret123');
});

test('shows error when email is empty', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });
  await user.click(submitBtn);

  const errorAlert = screen.getByRole('alert');
  expect(errorAlert).toHaveTextContent('Email is required.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when email format is invalid', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  await user.type(emailInput, 'invalid-email');
  await user.click(submitBtn);

  const errorAlert = screen.getByRole('alert');
  expect(errorAlert).toHaveTextContent('Enter a valid email address.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when password is empty', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  await user.type(emailInput, 'valid@example.com');
  await user.click(submitBtn);

  const errorAlert = screen.getByRole('alert');
  expect(errorAlert).toHaveTextContent('Password is required.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when confirm password is empty', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  await user.type(emailInput, 'valid@example.com');
  await user.type(passwordInput, 'secret123');
  await user.click(submitBtn);

  const errorAlert = screen.getByRole('alert');
  expect(errorAlert).toHaveTextContent('Confirm your password.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('shows error when passwords do not match', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  await user.type(emailInput, 'valid@example.com');
  await user.type(passwordInput, 'passwordA');
  await user.type(confirmPasswordInput, 'passwordB');
  await user.click(submitBtn);

  const errorAlert = screen.getByRole('alert');
  expect(errorAlert).toHaveTextContent('Passwords do not match.');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('succeeds after fixing mismatched password and submitting with Enter key', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  // Type mismatched values and submit
  await user.type(emailInput, 'test@example.com');
  await user.type(passwordInput, 'matching123');
  await user.type(confirmPasswordInput, 'different123');
  await user.click(submitBtn);

  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');

  // Correct confirm password and submit by pressing Enter
  await user.clear(confirmPasswordInput);
  await user.type(confirmPasswordInput, 'matching123{Enter}');

  // Form should now succeed
  const statusMsg = screen.getByRole('status');
  expect(statusMsg).toHaveTextContent('Demo only: no account was created.');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(emailInput).toHaveValue('test@example.com');
  expect(passwordInput).toHaveValue('');
  expect(confirmPasswordInput).toHaveValue('');
});

test('clears error message when confirm password is edited', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  // Trigger error
  await user.click(submitBtn);
  expect(screen.getByRole('alert')).toBeInTheDocument();

  // Edit confirm password to clear error
  await user.type(confirmPasswordInput, 'a');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('clears error message when email is edited', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  // Trigger error
  await user.click(submitBtn);
  expect(screen.getByRole('alert')).toBeInTheDocument();

  // Edit email to clear error
  await user.type(emailInput, 'user@example.com');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('clears success message when confirm password is edited', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  // Submit valid form
  await user.type(emailInput, 'user@example.com');
  await user.type(passwordInput, 'validPass123');
  await user.type(confirmPasswordInput, 'validPass123');
  await user.click(submitBtn);

  expect(screen.getByRole('status')).toBeInTheDocument();

  // Edit confirm password to verify removal of status
  await user.type(confirmPasswordInput, 'x');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('clears success message when password is edited', async () => {
  const user = userEvent.setup();
  render(<RegisterForm />);

  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/^Password/i);
  const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i);
  const submitBtn = screen.getByRole('button', { name: 'Create demo account' });

  // Submit valid form
  await user.type(emailInput, 'user@example.com');
  await user.type(passwordInput, 'validPass123');
  await user.type(confirmPasswordInput, 'validPass123');
  await user.click(submitBtn);

  expect(screen.getByRole('status')).toBeInTheDocument();

  // Edit password to verify removal of status
  await user.type(passwordInput, 'newPass123');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
