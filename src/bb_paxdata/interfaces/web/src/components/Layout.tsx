import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useUIStore } from '@/store/uiStore';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { Toast } from './Toast';
import { LoginForm } from './LoginForm';

export const Layout = () => {
  const { isAuthenticated } = useAuth();
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toasts = useUIStore((s) => s.toasts);
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
      root.classList.remove('dark');
    } else {
      root.classList.add('dark');
      root.classList.remove('light');
    }
  }, [theme]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] flex items-center justify-center">
        <LoginForm />
        <Toast toasts={toasts} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] flex">
      <Sidebar />
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ${sidebarCollapsed ? 'ml-16' : 'ml-60'}`}
      >
        <TopBar />
        <main className="flex-1 p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
      <Toast toasts={toasts} />
    </div>
  );
};
