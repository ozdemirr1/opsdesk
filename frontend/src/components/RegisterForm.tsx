import { useState } from 'react';
import type { FormEvent, ChangeEvent } from 'react';

type Feedback = {
  kind: 'error' | 'success';
  message: string;
} | null;

export default function RegisterForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);

  // Handle email changes and clear previous feedback
  const handleEmailChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEmail(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  // Handle password changes and clear previous feedback
  const handlePasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPassword(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  // Handle confirm password changes and clear previous feedback
  const handleConfirmPasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setConfirmPassword(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  // Handle form submission
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const trimmedEmail = email.trim();

    // 1. Validation: Empty email
    if (!trimmedEmail) {
      setFeedback({ kind: 'error', message: 'Email is required.' });
      return;
    }

    // 2. Validation: Simple email format check
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setFeedback({ kind: 'error', message: 'Enter a valid email address.' });
      return;
    }

    // 3. Validation: Empty password
    if (password === '') {
      setFeedback({ kind: 'error', message: 'Password is required.' });
      return;
    }

    // 4. Validation: Empty confirm password
    if (confirmPassword === '') {
      setFeedback({ kind: 'error', message: 'Confirm your password.' });
      return;
    }

    // 5. Validation: Passwords mismatch
    if (password !== confirmPassword) {
      setFeedback({ kind: 'error', message: 'Passwords do not match.' });
      return;
    }

    // Success state for demo
    setFeedback({ kind: 'success', message: 'Demo only: no account was created.' });
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="register-email">
          Email <span className="required-mark" aria-hidden="true">*</span>
        </label>
        <input
          id="register-email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={handleEmailChange}
        />
      </div>

      <div className="form-group">
        <label htmlFor="register-password">
          Password <span className="required-mark" aria-hidden="true">*</span>
        </label>
        <input
          id="register-password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={handlePasswordChange}
        />
      </div>

      <div className="form-group">
        <label htmlFor="register-confirm-password">
          Confirm password <span className="required-mark" aria-hidden="true">*</span>
        </label>
        <input
          id="register-confirm-password"
          type="password"
          name="confirm-password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={handleConfirmPasswordChange}
        />
      </div>

      <button type="submit" className="submit-btn">
        Create demo account
      </button>

      {feedback && (
        <div
          className={`feedback-message ${feedback.kind}`}
          role={feedback.kind === 'error' ? 'alert' : 'status'}
        >
          {feedback.message}
        </div>
      )}
    </form>
  );
}
