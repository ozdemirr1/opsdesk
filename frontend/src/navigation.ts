import { useSyncExternalStore } from 'react';

export type Route =
  | { screen: 'home' | 'login' | 'register' | 'organizations' | 'missing' }
  | { screen: 'workspace'; organizationId: number; ticketId?: number };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/u, '') || '/';
  const screens = { '/': 'home', '/login': 'login', '/register': 'register', '/organizations': 'organizations' } as const;
  if (Object.hasOwn(screens, path)) return { screen: screens[path as keyof typeof screens] };
  const match = /^\/organizations\/([1-9]\d*)\/tickets(?:\/([1-9]\d*))?$/u.exec(path);
  if (match) {
    const organizationId = Number(match[1]);
    const ticketId = match[2] ? Number(match[2]) : undefined;
    if (Number.isSafeInteger(organizationId) && (ticketId === undefined || Number.isSafeInteger(ticketId))) {
      return { screen: 'workspace', organizationId, ticketId };
    }
  }
  return { screen: 'missing' };
}

const subscribe = (listener: () => void) => {
  window.addEventListener('hashchange', listener);
  window.addEventListener('popstate', listener);
  return () => {
    window.removeEventListener('hashchange', listener);
    window.removeEventListener('popstate', listener);
  };
};
export function useRoute(): Route {
  return parseRoute(useSyncExternalStore(subscribe, () => window.location.hash, () => ''));
}
export function navigate(path: string) {
  // Only known internal destinations can enter browser history.
  if (parseRoute(`#${path}`).screen === 'missing') return;
  window.history.pushState(null, '', `#${path}`);
  window.dispatchEvent(new Event('hashchange'));
}
export function ticketPath(organizationId: number, ticketId?: number) {
  return `/organizations/${organizationId}/tickets${ticketId === undefined ? '' : `/${ticketId}`}`;
}
