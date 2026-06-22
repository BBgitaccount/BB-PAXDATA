import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@/store/uiStore';
import { useAuth } from '@/hooks/useAuth';
import {
  LayoutDashboard,
  ClipboardList,
  FileText,
  BarChart3,
  Settings,
  GitCompare,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Network,
  Clock,
  TrendingUp,
  Activity,
  Zap,
  Users,
} from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import type { tr } from '@/i18n/tr';
import { cn } from '@/utils/helpers';

const navSections: Array<{
  group: keyof typeof tr;
  items: Array<{
    id: string;
    label: keyof typeof tr;
    path: string;
    icon: any;
  }>;
}> = [
  {
    group: 'nav.group.general',
    items: [
      {
        id: 'dashboard',
        label: 'nav.dashboard',
        path: '/',
        icon: LayoutDashboard,
      },
      {
        id: 'speakers',
        label: 'nav.speakers',
        path: '/speakers',
        icon: Users,
      },
      {
        id: 'discourse',
        label: 'nav.discourse',
        path: '/discourse',
        icon: Network,
      },
      {
        id: 'anomalies',
        label: 'nav.anomalies',
        path: '/anomalies',
        icon: Clock,
      },
      { id: 'drift', label: 'nav.drift', path: '/drift', icon: TrendingUp },
      { id: 'health', label: 'nav.health', path: '/health', icon: Activity },
      { id: 'monitor', label: 'nav.monitor', path: '/monitor', icon: Zap },
    ],
  },
  {
    group: 'nav.group.logic',
    items: [
      {
        id: 'logic-queue',
        label: 'nav.logic_queue',
        path: '/hitl-logic/queue',
        icon: ClipboardList,
      },
      {
        id: 'logic-audit',
        label: 'nav.logic_audit',
        path: '/hitl-logic/audit',
        icon: FileText,
      },
      {
        id: 'logic-calib',
        label: 'nav.logic_calib',
        path: '/hitl-logic/calibration',
        icon: BarChart3,
      },
      {
        id: 'logic-prompts',
        label: 'nav.logic_prompts',
        path: '/hitl-logic/prompts',
        icon: BookOpen,
      },
    ],
  },
  {
    group: 'nav.group.ai',
    items: [
      {
        id: 'ai-queue',
        label: 'nav.ai_queue',
        path: '/hitl-ai/queue',
        icon: ClipboardList,
      },
      {
        id: 'comparison',
        label: 'nav.comparison',
        path: '/hitl-ai/comparison',
        icon: GitCompare,
      },
      {
        id: 'settings',
        label: 'nav.settings',
        path: '/settings',
        icon: Settings,
      },
    ],
  },
];

export const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { t } = useTranslation();
  useAuth();

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-screen bg-[var(--bg-secondary)] border-r border-hair border-carbon-550 z-50 flex flex-col transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-60',
      )}
    >
      <div className="h-16 border-b border-hair border-carbon-550 flex items-center px-4">
        {!sidebarCollapsed && (
          <div className="flex items-center">
            <div className="flex flex-col">
              <span className="text-xs font-semibold tracking-tight text-carbon-50 leading-tight">
                PAXDATA
              </span>
              <span className="text-micro text-carbon-450 tracking-diplomatic">
                DASHBOARD SERVICE
              </span>
            </div>
          </div>
        )}
        {sidebarCollapsed && <div className="mx-auto flex items-center justify-center" />}
      </div>

      <nav className="flex-1 py-4 overflow-y-auto space-y-4">
        {navSections.map((section, idx) => (
          <div key={section.group} className="space-y-1">
            {idx > 0 && <div className="border-t border-hair border-carbon-550/40 my-3 mx-4" />}
            {!sidebarCollapsed && (
              <div className="px-4 py-1.5 text-micro font-semibold text-carbon-400 tracking-wider select-none">
                {t(section.group)}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = isActive(item.path);
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.path)}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-swift relative group',
                      active
                        ? 'text-carbon-50 bg-carbon-800'
                        : 'text-carbon-300 hover:text-carbon-100 hover:bg-carbon-800/50',
                    )}
                  >
                    {active && (
                      <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-carbon-50" />
                    )}
                    <Icon
                      className={cn('w-4 h-4 flex-shrink-0', active && 'text-carbon-50')}
                      strokeWidth={1.5}
                    />
                    {!sidebarCollapsed && (
                      <span className="font-medium tracking-tight">{t(item.label)}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-hair border-carbon-550 p-3">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center p-2 text-carbon-400 hover:text-carbon-200 transition-colors"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
};
