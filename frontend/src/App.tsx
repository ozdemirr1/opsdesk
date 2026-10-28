import { useCallback, useEffect, useRef, useState } from 'react';
import AppHeader from './components/AppHeader';
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import { getCurrentUser } from './api/identity';
import type { Session } from './types/session';
import Organizations from './components/Organizations';
import Workspace from './components/Workspace';
import { navigate, useRoute } from './navigation';
import './App.css';


function App() {
  const route = useRoute();
  const [sessionEpoch, setSessionEpoch] = useState(0);
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

  const handleSignOut = useCallback(() => {
    // Abort pending session check and reset state
    if (checkAbortControllerRef.current) {
      checkAbortControllerRef.current.abort();
      checkAbortControllerRef.current = null;
    }
    sessionRef.current = null;
    setIsCheckingSession(false);
    setSession(null);
    navigate('/login');
    setSessionError(null);
  }, []);

  const handleExpired = useCallback(() => {
    handleSignOut();
    setSessionError('Your session is no longer valid. Please sign in again.');
  }, [handleSignOut]);

  const handleAuthenticated = (newSession: Session) => {
    // Invalidate any stale in-flight check when authenticating
    if (checkAbortControllerRef.current) {
      checkAbortControllerRef.current.abort();
      checkAbortControllerRef.current = null;
    }
    setSessionEpoch(value => value + 1);
    sessionRef.current = newSession;
    setIsCheckingSession(false);
    setSession(newSession);
    setSessionError(null);
    // A guarded deep link stays in place; ordinary login opens the directory.
    if (route.screen !== 'organizations' && route.screen !== 'workspace') {
      navigate('/organizations');
    }
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
          navigate('/login');
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
          navigate('/login');
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

  const privateRoute = route.screen === 'organizations' || route.screen === 'workspace';
  // Root opens the user's directory only after authentication. Learning fixtures
  // are not part of the product navigation.
  const activeScreen = privateRoute && !session ? 'login'
    : route.screen === 'home' ? (session ? 'organizations' : 'login')
    : session && route.screen === 'register' ? 'organizations' : route.screen;

  return (
    <>
      <AppHeader
        productName="OpsDesk"
        subtitle="Support ticket workspace"
      />

      <nav aria-label="Screens" className="screen-nav">
        {!session ? <>
          <button type="button" onClick={() => navigate('/login')} aria-pressed={activeScreen === 'login'}>Login</button>
          <button type="button" onClick={() => navigate('/register')} aria-pressed={activeScreen === 'register'}>Register</button>
        </> : <>
          <button type="button" onClick={() => navigate('/organizations')} aria-pressed={activeScreen === 'organizations' || activeScreen === 'workspace'}>Workspaces</button>
          <button type="button" onClick={() => navigate('/login')} aria-pressed={activeScreen === 'login'}>Account</button>
        </>}
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
        {session && activeScreen === 'organizations' && <Organizations key={sessionEpoch} token={session.accessToken} onExpired={handleExpired} />}
        {session && route.screen === 'workspace' && <Workspace key={`${sessionEpoch}:${route.organizationId}`} token={session.accessToken}
          organizationId={route.organizationId} ticketId={route.ticketId} onExpired={handleExpired} />}
        {route.screen === 'missing' && <section><h2>Page not found</h2><a href="#/">Go to home</a></section>}
        {privateRoute && !session && <p>Sign in to open this workspace. Reloading clears your session.</p>}
        {sessionError && <p role="alert">{sessionError}</p>}

        {activeScreen === 'login' && (
          <section>
            <h2>{session ? 'Account' : 'Login'}</h2>
            {session ? (
              <p role="status">Signed in as {session.user.email}</p>
            ) : (
              <>
                <p>Sign in to access your workspaces and tickets.</p>
                <p className="session-note">Your session stays in this tab. Reloading requires signing in again.</p>
                <LoginForm onAuthenticated={handleAuthenticated} />
              </>
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
