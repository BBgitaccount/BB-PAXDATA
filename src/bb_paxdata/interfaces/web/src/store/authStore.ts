import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, PermissionLevel } from '@/types';
import { UNAUTHORIZED_EVENT } from '@/services/apiClient';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (user: User) => void;
  logout: () => void;
  hasPermission: (level: PermissionLevel) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      login: (user) => {
        localStorage.setItem('paxdata_token', user.token);
        set({ user, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('paxdata_token');
        set({ user: null, isAuthenticated: false });
      },
      hasPermission: (level) => {
        const user = get().user;
        if (!user) return false;
        const hierarchy: Record<PermissionLevel, number> = {
          view: 0,
          verdict: 1,
          correct: 2,
          escalate: 3,
          admin: 4,
        };
        const userLevel = Math.max(...user.roles.map((r) => hierarchy[r]));
        return userLevel >= hierarchy[level];
      },
    }),
    { name: 'bb-paxdata-auth' },
  ),
);

// ─── Global 401 listener ─────────────────────────────────────────────────────
// Listen for UNAUTHORIZED_EVENT dispatched by apiClient on every 401 response.
// Automatically logs the user out and reloads to the login screen.
// The `_paxdata_401_listener` flag prevents duplicate bindings on HMR.
declare global {
  interface Window {
    _paxdata_401_listener?: boolean;
  }
}
if (typeof window !== 'undefined' && !window._paxdata_401_listener) {
  window._paxdata_401_listener = true;
  window.addEventListener(UNAUTHORIZED_EVENT, () => {
    useAuthStore.getState().logout();
    // Redirect to root which will show the LoginForm
    window.location.replace('/');
  });
}
