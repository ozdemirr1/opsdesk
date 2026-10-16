import { useState, useRef, useEffect } from 'react';
import type { FormEvent, ChangeEvent } from 'react';
import { loginUser, getCurrentUser } from '../api/identity';
import type { Session } from '../types/session';

type Feedback = {
  kind: 'error' | 'success';
  message: string;
} | null;

type LoginFormProps = {
  onAuthenticated: (session: Session) => void;
};

export default function LoginForm({ onAuthenticated }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Abort pending request when unmounted
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
    const isAscii = [...trimmedEmail].every((char) => char.charCodeAt(0) <= 127);
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

    // Normalize password using NFC without trimming and count Unicode code points
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

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setFeedback(null);
    setIsSubmitting(true);

    // Step 1: Send login request
    const loginResult = await loginUser(
      { email: trimmedEmail, password: normalizedPassword },
      controller.signal
    );

    // If controller changed or was aborted, ignore response
    if (abortControllerRef.current !== controller || controller.signal.aborted) {
      return;
    }

    if (!loginResult.ok) {
      abortControllerRef.current = null;
      setIsSubmitting(false);

      if (loginResult.kind === 'aborted') return;

      if (loginResult.status === 401) {
        setFeedback({
          kind: 'error',
          message: 'Email or password is incorrect.',
        });
        return;
      }

      setFeedback({
        kind: 'error',
        message: loginResult.message,
      });
      return;
    }

    // Login successful: clear password input and request user profile
    setPassword('');
    const token = loginResult.data.access_token;

    // Fetch user profile with the same abort signal
    const profileResult = await getCurrentUser(token, controller.signal);

    if (abortControllerRef.current !== controller || controller.signal.aborted) {
      return;
    }

    abortControllerRef.current = null;
    setIsSubmitting(false);

    if (!profileResult.ok) {
      if (profileResult.kind === 'aborted') return;

      setFeedback({
        kind: 'error',
        message: profileResult.message,
      });
      return;
    }

    if (!profileResult.data.is_active) {
      setFeedback({
        kind: 'error',
        message: 'Account is inactive. Please contact support.',
      });
      return;
    }

    // Both steps succeeded: notify parent component
    onAuthenticated({
      accessToken: token,
      user: profileResult.data,
    });
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="login-email">
          Email <span className="required-mark" aria-hidden="true">*</span>
        </label>
        <input
          id="login-email"
          type="email"
          name="email"
          autoComplete="username"
          required
          disabled={isSubmitting}
          value={email}
          onChange={handleEmailChange}
        />
      </div>

      <div className="form-group">
        <label htmlFor="login-password">
          Password <span className="required-mark" aria-hidden="true">*</span>
        </label>
        <input
          id="login-password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          disabled={isSubmitting}
          value={password}
          onChange={handlePasswordChange}
        />
      </div>

      <button type="submit" className="submit-btn" disabled={isSubmitting}>
        {isSubmitting ? 'Signing in...' : 'Sign in'}
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
