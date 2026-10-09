import { useState } from 'react';
import type { FormEvent, ChangeEvent } from 'react';

type Feedback = {
  kind: 'error' | 'success';
  message: string;
} | null;

export default function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);

  // Handle email input changes and clear existing feedback
  const handleEmailChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEmail(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  // Handle password input changes and clear existing feedback
  const handlePasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPassword(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  // Handle form submission
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const trimmedEmail = email.trim();

    // Validation: Empty email
    if (!trimmedEmail) {
      setFeedback({ kind: 'error', message: 'Email is required.' });
      return;
    }

    // Validation: Invalid email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setFeedback({ kind: 'error', message: 'Enter a valid email address.' });
      return;
    }

    // Validation: Empty password
    if (password === '') {
      setFeedback({ kind: 'error', message: 'Password is required.' });
      return;
    }

    // Success state
    setFeedback({ kind: 'success', message: 'Demo only: no sign-in request was sent.' });
    setPassword('');
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="login-email">Email <span className="required-mark" aria-hidden="true">*</span></label>
        <input
          id="login-email"
          type="email"
          name="email"
          autoComplete="username"
          required
          value={email}
          onChange={handleEmailChange}
        />
      </div>

      <div className="form-group">
        <label htmlFor="login-password">Password <span className="required-mark" aria-hidden="true">*</span></label>
        <input
          id="login-password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={handlePasswordChange}
        />
      </div>

      <button type="submit" className="submit-btn">Continue demo</button>

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
