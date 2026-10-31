import { useRef, type ReactNode } from 'react';
import AppHeader from './AppHeader';

type Props = {
  email?: string;
  navigation: ReactNode;
  children: ReactNode;
};

/** The same navigation remains keyboard-accessible on desktop and mobile. */
export default function AppShell({ email, navigation, children }: Props) {
  const main = useRef<HTMLElement>(null);
  return (
    <div className={email ? 'app-shell' : 'auth-shell'}>
      <a className="skip-link" href="#main-content" onClick={event => {
        event.preventDefault();
        main.current?.focus();
      }}>Skip to content</a>
      <aside className={email ? 'app-sidebar' : 'auth-intro'} aria-label="OpsDesk">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">O<span /></span>
          <AppHeader productName="OpsDesk" subtitle="Support ticket workspace" />
        </div>
        {email ? <>
          <p className="nav-caption">WORKSPACE</p>
          {navigation}
          <div className="sidebar-profile">
            <span className="profile-avatar" aria-hidden="true">{email.slice(0, 1).toUpperCase()}</span>
            <div className="min-w-0"><p className="text-xs font-semibold text-muted">Signed in</p><p className="profile-email">{email}</p></div>
          </div>
        </> : <div className="auth-story">
          <p className="eyebrow">YOUR SUPPORT WORKSPACE</p>
          <h2>Less scattered.<br /><span>More focused.</span></h2>
          <p>Keep your team’s tickets, conversations and priorities in one place.</p>
          <ul className="auth-features">
            <li><span aria-hidden="true">01</span> Choose your workspace</li>
            <li><span aria-hidden="true">02</span> Follow the conversation</li>
            <li><span aria-hidden="true">03</span> Keep priorities clear</li>
          </ul>
          <p className="preview-label">OpsDesk · Early preview</p>
        </div>}
      </aside>
      <div className={email ? 'app-content' : 'auth-content'}>
        {email && <div className="app-topbar"><span>Support workspace</span><span className="preview-tag">Early preview</span></div>}
        <main ref={main} id="main-content" tabIndex={-1} className="min-w-0">
          {!email && navigation}
          {children}
        </main>
      </div>
    </div>
  );
}
