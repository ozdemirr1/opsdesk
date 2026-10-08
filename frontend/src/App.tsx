import { useState } from 'react';
import AppHeader from './components/AppHeader';
import TicketList from './components/TicketList';
import { mockTickets } from './data/mockTickets';
import './App.css';

type Screen = 'tickets' | 'login' | 'register';

function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>('tickets');

  return (
    <>
      <AppHeader
        productName="OpsDesk"
        subtitle="Support ticket workspace"
      />

      <nav aria-label="Demo screens" className="screen-nav">
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
      </nav>

      <main>
        <p className="mock-note">Demo screens use mock data.</p>

        {activeScreen === 'tickets' && (
          <section>
            <h2>Tickets</h2>
            <TicketList tickets={mockTickets} />
          </section>
        )}

        {activeScreen === 'login' && (
          <section>
            <h2>Login</h2>
            <p>Sign in to your workspace.</p>
          </section>
        )}

        {activeScreen === 'register' && (
          <section>
            <h2>Register</h2>
            <p>Create your account.</p>
          </section>
        )}
      </main>
    </>
  );
}

export default App;
