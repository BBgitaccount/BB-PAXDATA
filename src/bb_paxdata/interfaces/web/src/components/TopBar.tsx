import { useAuth } from '@/hooks/useAuth';
import { useUIStore } from '@/store/uiStore';
import { useTranslation } from '@/hooks/useTranslation';
import { Bell, LogOut, User, Sun, Moon } from 'lucide-react';

export const TopBar = () => {
  const { user, logout } = useAuth();
  const addToast = useUIStore((s) => s.addToast);
  const { theme, toggleTheme } = useUIStore();
  const { t, language, setLanguage } = useTranslation();

  const handleLogout = () => {
    logout();
    addToast({ type: 'info', message: t('topbar.logout_toast') });
  };

  return (
    <header className="h-16 bg-[var(--bg-primary)] border-b border-hair border-carbon-550 flex items-center justify-between px-8 sticky top-0 z-40">
      <div />

      <div className="flex items-center gap-6">
        {/* Notification Bell */}
        <button className="relative text-carbon-300 hover:text-carbon-50 transition-colors cursor-pointer">
          <Bell className="w-4 h-4" strokeWidth={1.5} />
          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-carbon-50 text-carbon-950 text-micro flex items-center justify-center font-mono font-bold">
            3
          </span>
        </button>

        {/* Premium Button Group: Language & Theme */}
        <div className="flex items-center border border-hair border-carbon-550 overflow-hidden">
          {/* Language Button */}
          <button
            onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}
            className="w-[36px] h-[32px] flex items-center justify-center text-micro font-mono font-bold tracking-widest bg-carbon-700 text-carbon-50 hover:bg-carbon-800 transition-colors duration-150 border-r border-hair border-carbon-550 cursor-pointer"
            title={language === 'tr' ? 'Switch to English' : "Türkçe'ye geç"}
          >
            {language.toUpperCase()}
          </button>

          {/* Theme Button */}
          <button
            onClick={toggleTheme}
            className="w-[36px] h-[32px] flex items-center justify-center text-carbon-400 hover:text-carbon-50 hover:bg-carbon-800 transition-colors duration-150 cursor-pointer"
            title={theme === 'dark' ? t('topbar.light_mode') : t('topbar.dark_mode')}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4" strokeWidth={1.5} />
            ) : (
              <Moon className="w-4 h-4" strokeWidth={1.5} />
            )}
          </button>
        </div>

        {/* User Profile */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-carbon-50 font-medium tracking-tight">
              {user?.reviewer_id}
            </div>
            <div className="text-micro text-carbon-400 uppercase tracking-diplomatic">
              {user?.roles.join(' · ')}
            </div>
          </div>
          <div className="w-8 h-8 bg-carbon-800 border border-hair border-carbon-550 flex items-center justify-center">
            <User className="w-4 h-4 text-carbon-300" strokeWidth={1.5} />
          </div>
          <button
            onClick={handleLogout}
            className="text-carbon-400 hover:text-carbon-50 transition-colors cursor-pointer"
            title={t('topbar.logout')}
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </header>
  );
};
