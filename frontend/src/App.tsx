import { useEffect, useRef, useState } from 'react';
import AppHeader from './components/AppHeader';
import TicketTable from './components/TicketTable';
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import { getCurrentUser } from './api/identity';
import { mockTickets } from './data/mockTickets';
import type { Session } from './types/session';
import './App.css';

type Screen = 'tickets' | 'login' | 'register';

function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>('tickets');
  const [session, setSession] = useState<Session | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const checkAbortControllerRef = useRef<AbortController | null>(null);
  const sessionRef = useRef<Session | null>(null);

  useEffect(() => {
    return () => {
      // Abort any ongoing session check on unmount
      if (checkAbortControllerRef.current) {
        checkAbortControllerRef.current.abort();
        checkAbortControllerRef.current = null;
      }
    };
  }, []);

  const handleSignOut = () => {
    // Abort pending session check and reset state
    if (checkAbortControllerRef.current) {
      checkAbortControllerRef.current.abort();
      checkAbortControllerRef.current = null;
    }
    sessionRef.current = null;
    setIsCheckingSession(false);
    setSession(null);
    setActiveScreen('login');
    setSessionError(null);
  };

  const handleAuthenticated = (newSession: Session) => {
    // Invalidate any stale in-flight check when authenticating
    if (checkAbortControllerRef.current) {
      checkAbortControllerRef.current.abort();
      checkAbortControllerRef.current = null;
    }
    sessionRef.current = newSession;
    setIsCheckingSession(false);
    setSession(newSession);
    setSessionError(null);
  };

  const handleCheckSession = async () => {
    if (!session || isCheckingSession) {
      return;
    }

    // Cancel existing controller if any
    if (checkAbortControllerRef.current) {
      checkAbortControllerRef.current.abort();
    }

    const controller = new AbortController();
    checkAbortControllerRef.current = controller;
    const currentToken = session.accessToken;

    setIsCheckingSession(true);
    setSessionError(null);

    try {
      const result = await getCurrentUser(currentToken, controller.signal);

      // Verify the request is still valid and session has not changed
      if (
        controller.signal.aborted ||
        checkAbortControllerRef.current !== controller ||
        sessionRef.current?.accessToken !== currentToken
      ) {
        return;
      }

      if (result.ok) {
        if (result.data.is_active) {
          // Valid active profile: update user info and keep session
          const updatedSession: Session = {
            accessToken: currentToken,
            user: result.data,
          };
          sessionRef.current = updatedSession;
          setSession(updatedSession);
          setSessionError(null);
        } else {
          // Valid profile but inactive: clear session and redirect to login
          sessionRef.current = null;
          setSession(null);
          setActiveScreen('login');
          setSessionError('Your session is no longer valid. Please sign in again.');
        }
      } else {
        if (result.kind === 'aborted') {
          return;
        }

        if (result.kind === 'http' && result.status === 401) {
          // 401 Unauthorized: clear session and redirect to login
          sessionRef.current = null;
          setSession(null);
          setActiveScreen('login');
          setSessionError('Your session is no longer valid. Please sign in again.');
        } else {
          // Network, 500 or invalid response: keep session and display safe error message
          setSessionError('Unable to verify session. Please try again.');
        }
      }
    } catch {
      if (
        controller.signal.aborted ||
        checkAbortControllerRef.current !== controller ||
        sessionRef.current?.accessToken !== currentToken
      ) {
        return;
      }
      setSessionError('Unable to verify session. Please try again.');
    } finally {
      if (checkAbortControllerRef.current === controller) {
        checkAbortControllerRef.current = null;
        setIsCheckingSession(false);
      }
    }
  };

  return (
    <>
      <AppHeader
        productName="OpsDesk"
        subtitle="Support ticket workspace"
      />

      <nav aria-label="Screens" className="screen-nav">
        <button
          type="button"
          onClick={() => setActiveScreen('tickets')}
          aria-pressed={activeScreen === 'tickets'}
        >
          Tickets
        </button>
        <button
          type="button"
          onClick={() => setActiveScreen('login')}
          aria-pressed={activeScreen === 'login'}
        >
          Login
        </button>
        <button
          type="button"
          onClick={() => setActiveScreen('register')}
          aria-pressed={activeScreen === 'register'}
        >
          Register
        </button>
        {session && (
          <>
            <button
              type="button"
              onClick={handleCheckSession}
              disabled={isCheckingSession}
            >
              Check session
            </button>
            <button
              type="button"
              onClick={handleSignOut}
            >
              Sign out
            </button>
          </>
        )}
      </nav>

      <main>
        <p className="mock-note">
          Tickets use mock data. Registration and login connect to the live API.
        </p>

        {sessionError && <p role="alert">{sessionError}</p>}

        {activeScreen === 'tickets' && (
          <section>
            <h2>Tickets</h2>
            <TicketTable tickets={mockTickets} />
          </section>
        )}

        {activeScreen === 'login' && (
          <section>
            <h2>Login</h2>
            {session ? (
              <p role="status">Signed in as {session.user.email}</p>
            ) : (
              <LoginForm onAuthenticated={handleAuthenticated} />
            )}
          </section>
        )}

        {activeScreen === 'register' && (
          <section>
            <h2>Register</h2>
            <RegisterForm />
          </section>
        )}
      </main>
    </>
  );
}

export default App;
