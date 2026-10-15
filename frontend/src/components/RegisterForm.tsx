import { useState, useRef, useEffect } from 'react';
import type { FormEvent, ChangeEvent } from 'react';
import { registerUser } from '../api/identity';

type Feedback = {
  kind: 'error' | 'success';
  message: string;
} | null;

export default function RegisterForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Abort pending request on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current !== null) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  const handleEmailChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEmail(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  const handlePasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPassword(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  const handleConfirmPasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setConfirmPassword(e.currentTarget.value);
    if (feedback) setFeedback(null);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Prevent concurrent submissions if a request is already in-flight
    if (abortControllerRef.current !== null) {
      return;
    }

    const trimmedEmail = email.trim();

    // 1. Validation: Empty email
    if (!trimmedEmail) {
      setFeedback({ kind: 'error', message: 'Email is required.' });
      return;
    }

    // 2. Validation: ASCII-only, max 254 chars, basic format check
    const isAscii = Array.from(trimmedEmail).every(
      (character) => character.charCodeAt(0) <= 127
    );
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!isAscii || trimmedEmail.length > 254 || !emailRegex.test(trimmedEmail)) {
      setFeedback({ kind: 'error', message: 'Enter a valid email address.' });
      return;
    }

    // 3. Validation: Empty password
    if (password === '') {
      setFeedback({ kind: 'error', message: 'Password is required.' });
      return;
    }

    // Normalize password using NFC and calculate Unicode code point length
    const normalizedPassword = password.normalize('NFC');
    const passwordLength = Array.from(normalizedPassword).length;

    // 4. Validation: Password length (15 to 128 Unicode code points)
    if (passwordLength < 15 || passwordLength > 128) {
      setFeedback({
        kind: 'error',
        message: 'Password must be between 15 and 128 characters.',
      });
      return;
    }

    // 5. Validation: Empty confirm password
    if (confirmPassword === '') {
      setFeedback({ kind: 'error', message: 'Confirm your password.' });
      return;
    }

    // 6. Validation: Normalized password mismatch
    const normalizedConfirmPassword = confirmPassword.normalize('NFC');
    if (normalizedPassword !== normalizedConfirmPassword) {
      setFeedback({ kind: 'error', message: 'Passwords do not match.' });
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setFeedback(null);
    setIsSubmitting(true);

    const result = await registerUser(
      { email: trimmedEmail, password: normalizedPassword },
      controller.signal
    );

    // If controller changed or was aborted (e.g. unmounted), do not update state
    if (abortControllerRef.current !== controller || controller.signal.aborted) {
      return;
    }

    abortControllerRef.current = null;
    setIsSubmitting(false);

    if (result.ok) {
      setFeedback({
        kind: 'success',
        message: 'Account created. You are not signed in.',
      });
      setPassword('');
      setConfirmPassword('');
      return;
    }

    if (result.kind === 'http') {
      setFeedback({
        kind: 'error',
        message: result.message,
      });
      return;
    }

    if (result.kind === 'network' || result.kind === 'invalid_response') {
      setFeedback({
        kind: 'error',
        message:
          'Registration could not be confirmed. The account may have been created.',
      });
      return;
    }
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
          disabled={isSubmitting}
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
          disabled={isSubmitting}
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
          disabled={isSubmitting}
          value={confirmPassword}
          onChange={handleConfirmPasswordChange}
        />
      </div>

      <button type="submit" className="submit-btn" disabled={isSubmitting}>
        {isSubmitting ? 'Creating account...' : 'Create account'}
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
