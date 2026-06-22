import { create } from 'zustand';
import type { User, PermissionLevel } from '@/types';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (user: User) => void;
  logout: () => void;
  hasPermission: (level: PermissionLevel) => boolean;
}

export const useAuthStore = create<AuthState>()((set, _get) => ({
  user: {
    reviewer_id: 'admin',
    roles: ['admin'],
    token: '',
    scope_type: 'global',
    scope_value: '*',
  },
  isAuthenticated: true,
  login: (user) => {
    set({ user, isAuthenticated: true });
  },
  logout: () => {
    set({ user: null, isAuthenticated: false });
  },
  hasPermission: (_level) => {
    // Always return true for admin user
    return true;
  },
}));
