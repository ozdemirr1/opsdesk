import { useState } from 'react';
import AppHeader from './components/AppHeader';
import TicketList from './components/TicketList';
import LoginForm from './components/LoginForm';
import { mockTickets } from './data/mockTickets';
import './App.css';
import RegisterForm from './components/RegisterForm';

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
            <LoginForm />
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
