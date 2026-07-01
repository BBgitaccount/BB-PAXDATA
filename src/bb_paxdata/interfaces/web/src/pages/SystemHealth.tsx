import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Database,
  ExternalLink,
  Heart,
  Layers,
  LayoutGrid,
  RefreshCw,
  Server,
} from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { apiClient } from '@/services/apiClient';
import { cn } from '@/utils/helpers';

// ─── Types ────────────────────────────────────────────────────────────────────

interface DatabaseStatsResponse {
  database_mode: string;
  size_bytes: number;
  status: string;
  row_counts: Record<string, number>;
}

interface DashboardInfo {
  id: string;
  title: string;
  uid: string;
  slug: string;
  description: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DASHBOARDS: DashboardInfo[] = [
  {
    id: 'system_overview',
    title: 'Sistem Genel Görünüm',
    uid: 'bbpaxdata-system-overview',
    slug: 'system-overview',
    description:
      'CPU kullanımı, API gecikme süreleri, cache isabet oranları ve veri tabanı aktif bağlantıları.',
  },
  {
    id: 'hitl_review',
    title: 'HITL Review Analizi',
    uid: 'bbpaxdata-hitl-review',
    slug: 'hitl-review',
    description:
      'İnceleme kuyruğu bekleyen log adetleri, karar tipleri ve denetçi performans metrikleri.',
  },
  {
    id: 'formula_health',
    title: 'Formül Sağlık Durumu',
    uid: 'bbpaxdata-formula-health',
    slug: 'formula-health',
    description:
      'Formül bazlı hata ve yanlış alarm (False Positive) oranları ile sapma kalibrasyonları.',
  },
  {
    id: 'celery_workers',
    title: 'Celery Workers İş Yükü',
    uid: 'bbpaxdata-celery-workers',
    slug: 'celery-workers',
    description:
      'Arka plan asenkron görev durumları, Celery worker kuyruk yoğunlukları ve beat zamanlaması.',
  },
];

// Helper to format bytes to human readable sizes
const formatBytes = (bytes: number, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / k ** i).toFixed(dm)) + ' ' + sizes[i];
};

export const SystemHealth = () => {
  const toast = useToast();
  const { hasPermission } = useAuth();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<string>('system_overview');
  const isAdmin = hasPermission('admin');

  // Fetch Database Stats
  const statsQuery = useQuery({
    queryKey: ['database-stats'],
    queryFn: () => apiClient.get<DatabaseStatsResponse>('/api/v1/database/stats'),
    refetchInterval: (query) => {
      // Stop polling if we've hit an error (e.g. 401) — prevents log spam
      if (query.state.error) return false;
      return 15_000;
    },
    staleTime: 10_000,
    retry: 0, // Do not retry on 401 — the global handler will log the user out
    enabled: isAdmin,
  });

  const handleRefresh = () => {
    void statsQuery.refetch();
    toast.info('Sistem sağlığı verileri yenileniyor...');
  };

  // Find active dashboard details
  const activeDashboard = DASHBOARDS.find((d) => d.id === activeTab) || DASHBOARDS[0];

  // Restrict access to admin/escalate if required, but view level is standard
  if (!hasPermission('view')) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Activity className="w-8 h-8 text-carbon-500 mx-auto mb-4" />
          <p className="text-sm text-carbon-400">Bu sayfayı görüntülemek için yetkiniz yetersiz.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('health.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('health.desc')}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-xs border-carbon-600 hover:bg-carbon-800"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', statsQuery.isFetching && 'animate-spin')} />
          Yenile
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* KPI 1: General Status */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <Heart className="w-3.5 h-3.5" />
              Sistem Durumu
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2 flex items-center gap-2">
              <span
                className={cn(
                  'h-2.5 w-2.5 rounded-full flex-shrink-0',
                  !isAdmin
                    ? 'bg-carbon-500'
                    : statsQuery.data?.status === 'healthy'
                      ? 'bg-signal-pass'
                      : 'bg-signal-fail',
                )}
              />
              {!isAdmin
                ? 'YETKİ GEREKLİ'
                : statsQuery.data?.status === 'healthy'
                  ? 'AKTİF / SAĞLIKLI'
                  : 'DEGRADE'}
            </div>
          </div>
          <div className="text-4xs font-mono text-carbon-450 uppercase">
            Son Kontrol: {new Date().toLocaleTimeString()}
          </div>
        </div>

        {/* KPI 2: DB Mode */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5" />
              Veri Tabanı Modu
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2 uppercase">
              {!isAdmin ? 'YETKİ GEREKLİ' : statsQuery.data?.database_mode || '—'}
            </div>
          </div>
          <div className="text-4xs font-mono text-carbon-450 uppercase">PERSISTENCE ENGINE</div>
        </div>

        {/* KPI 3: DB Size */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5" />
              Disk Boyutu
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2">
              {!isAdmin
                ? 'YETKİ GEREKLİ'
                : statsQuery.data
                  ? formatBytes(statsQuery.data.size_bytes)
                  : '—'}
            </div>
          </div>
          <div className="text-4xs font-mono text-carbon-450 uppercase">
            Analitik Veri Büyüklüğü
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Row Counts Table */}
        <div className="lg:col-span-1 border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-carbon-400" />
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Tablo Kayıt Detayları
            </h3>
          </div>

          {!isAdmin ? (
            <div className="text-xs text-carbon-500 italic py-4 text-center">
              Veri tabanı istatistiklerini görüntülemek için admin yetkisi gereklidir.
            </div>
          ) : statsQuery.isPending ? (
            <div className="space-y-2 py-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-6 shimmer w-full" />
              ))}
            </div>
          ) : statsQuery.isError || !statsQuery.data ? (
            <div className="text-xs text-carbon-500 italic py-4 text-center">
              Tablo istatistikleri yüklenemedi.
            </div>
          ) : (
            <div className="overflow-y-auto max-h-[420px] pr-1">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-hair border-carbon-800 text-carbon-450 uppercase tracking-widest text-3xs font-semibold">
                    <th className="py-2">Tablo Adı</th>
                    <th className="py-2 text-right">Satır Sayısı</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hair divide-carbon-800 font-mono text-2xs">
                  {Object.entries(statsQuery.data.row_counts).map(([tableName, count]) => (
                    <tr key={tableName} className="hover:bg-carbon-850/30 transition-colors">
                      <td className="py-2.5 text-carbon-300 font-sans">{tableName}</td>
                      <td className="py-2.5 text-right text-carbon-100 font-tabular">
                        {count.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Grafana Dashboards Integration */}
        <div className="lg:col-span-2 border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <LayoutGrid className="w-4 h-4 text-carbon-400" />
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                Grafana Canlı İzleme Panelleri
              </h3>
            </div>

            <a
              href={`http://localhost:3000/d/${activeDashboard.uid}/${activeDashboard.slug}?orgId=1`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-3xs uppercase tracking-diplomatic text-carbon-300 hover:text-carbon-50 transition-colors font-medium border border-hair border-carbon-700 px-2.5 py-1 rounded"
            >
              PANELİ DIŞARIDA AÇ
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {/* Dashboard Tabs Selector */}
          <div className="flex gap-2 border-b border-hair border-carbon-800 pb-2">
            {DASHBOARDS.map((d) => (
              <button
                key={d.id}
                onClick={() => setActiveTab(d.id)}
                className={cn(
                  'px-3 py-1.5 text-2xs font-medium tracking-tight border-b-2 -mb-2.5 transition-all',
                  activeTab === d.id
                    ? 'border-carbon-50 text-carbon-50'
                    : 'border-transparent text-carbon-450 hover:text-carbon-200',
                )}
              >
                {d.title}
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <p className="text-2xs text-carbon-400 leading-relaxed font-sans italic">
              {activeDashboard.description}
            </p>

            {/* Grafana IFrame Embed */}
            <div className="relative aspect-video w-full bg-[var(--bg-primary)] border border-hair overflow-hidden rounded-none">
              <iframe
                src={`http://localhost:3000/d/${activeDashboard.uid}/${activeDashboard.slug}?orgId=1&kiosk=tv&theme=dark`}
                width="100%"
                height="100%"
                frameBorder="0"
                title={activeDashboard.title}
                className="absolute inset-0 w-full h-full"
                allowFullScreen
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
