import { expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

test('renders Tickets heading initially, no Login/Register headings, and Tickets button is selected', () => {
  render(<App />)

  // Check headings
  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Register', level: 2 })).not.toBeInTheDocument()

  // Check the selected button
  expect(screen.getByRole('button', { name: 'Tickets' })).toHaveAttribute('aria-pressed', 'true')
})

test('navigates to Login screen and returns to Tickets screen', async () => {
  const user = userEvent.setup()
  render(<App />)

  const loginBtn = screen.getByRole('button', { name: 'Login' })
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' })

  // Click the Login button
  await user.click(loginBtn)

  expect(screen.getByRole('heading', { name: 'Login', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument()
  expect(loginBtn).toHaveAttribute('aria-pressed', 'true')

  // Click the Tickets button again
  await user.click(ticketsBtn)

  expect(screen.getByRole('heading', { name: 'Tickets', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument()
  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'true')
})

test('shows only Register heading when navigated to Register, and other buttons are not selected', async () => {
  const user = userEvent.setup()
  render(<App />)

  const registerBtn = screen.getByRole('button', { name: 'Register' })
  const loginBtn = screen.getByRole('button', { name: 'Login' })
  const ticketsBtn = screen.getByRole('button', { name: 'Tickets' })

  // Click the Register button
  await user.click(registerBtn)

  expect(screen.getByRole('heading', { name: 'Register', level: 2 })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Tickets', level: 2 })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Login', level: 2 })).not.toBeInTheDocument()

  // Check button states
  expect(registerBtn).toHaveAttribute('aria-pressed', 'true')
  expect(ticketsBtn).toHaveAttribute('aria-pressed', 'false')
  expect(loginBtn).toHaveAttribute('aria-pressed', 'false')
})
