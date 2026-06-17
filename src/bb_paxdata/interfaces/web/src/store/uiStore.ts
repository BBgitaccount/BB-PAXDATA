import { create } from 'zustand';
import type { ToastMessage } from '@/types';

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  language: 'tr' | 'en';
  setLanguage: (lang: 'tr' | 'en') => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
  toasts: [],
  addToast: (toast) => {
    const id = Math.random().toString(36).slice(2, 9);
    set({ toasts: [...get().toasts, { ...toast, id }] });
    setTimeout(() => {
      set({ toasts: get().toasts.filter((t) => t.id !== id) });
    }, 4000);
  },
  removeToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),
  theme: (localStorage.getItem('bb_theme') as 'dark' | 'light') || 'dark',
  toggleTheme: () => {
    const nextTheme = get().theme === 'dark' ? 'light' : 'dark';
    set({ theme: nextTheme });
    localStorage.setItem('bb_theme', nextTheme);
  },
  language: (localStorage.getItem('bb_lang') as 'tr' | 'en') || 'tr',
  setLanguage: (lang) => {
    set({ language: lang });
    localStorage.setItem('bb_lang', lang);
  },
}));
