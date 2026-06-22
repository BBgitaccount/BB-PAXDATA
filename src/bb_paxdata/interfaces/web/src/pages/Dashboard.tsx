import { useEffect, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import { KpiCard } from '@/components/KpiCard';
import { FormulaHealthChart } from '@/components/FormulaHealthChart';
import { FormulaHealthTable } from '@/components/FormulaHealthTable';
import { BilateralHeatmap } from '@/components/BilateralHeatmap';
import { useToast } from '@/hooks/useToast';
import { useUIStore } from '@/store/uiStore';
import { useTranslation } from '@/hooks/useTranslation';
import type {
  KpiStats,
  FormulaHealth,
  DailyTrend,
  PriorityDistribution,
  TriggerDistribution,
  ConsensusDistribution,
  BilateralSentimentData,
  PanelTimelineEntry,
} from '@/types';
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  ShieldCheck,
  Edit3,
  TrendingUp,
  BarChart3,
  PieChart,
  Zap,
  Globe,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RePieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts';
import { isOfflineCapableError } from '@/services/offlineVerdictQueue';
import { readDashboardSnapshot, saveDashboardSnapshot } from '@/services/offlineDashboardCache';

export const Dashboard = () => {
  const toast = useToast();
  const [selectedPanel, setSelectedPanel] = useState<PanelTimelineEntry | null>(null);
  const theme = useUIStore((s) => s.theme);
  const { t } = useTranslation();

  const dashboardQuery = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: async () => {
      try {
        const [
          kpi,
          formulaHealth,
          dailyTrend,
          priorityDist,
          triggerDist,
          consensusDist,
          bilateral,
        ] = await Promise.all([
          apiClient.get<KpiStats>('/api/v1/dashboard/kpis'),
          apiClient.get<FormulaHealth[]>('/api/v1/dashboard/formulas/health'),
          apiClient.get<DailyTrend[]>('/api/v1/dashboard/trends'),
          apiClient.get<PriorityDistribution[]>('/api/v1/dashboard/priorities'),
          apiClient.get<TriggerDistribution[]>('/api/v1/dashboard/triggers'),
          apiClient.get<ConsensusDistribution[]>('/api/v1/dashboard/consensus'),
          apiClient.get<BilateralSentimentData[]>('/api/v1/dashboard/bilateral'),
        ]);

        const snapshot = {
          kpi,
          formulaHealth,
          dailyTrend,
          priorityDist,
          triggerDist,
          consensusDist,
          bilateral,
        };
        void saveDashboardSnapshot(snapshot);
        return snapshot;
      } catch (error) {
        if (isOfflineCapableError(error)) {
          const cachedSnapshot = await readDashboardSnapshot();
          if (cachedSnapshot) {
            return cachedSnapshot;
          }
        }

        throw error;
      }
    },
  });

  // Timeline query — panel list for time slider
  const timelineQuery = useQuery({
    queryKey: ['bilateral-timeline'],
    queryFn: () => apiClient.get<PanelTimelineEntry[]>('/api/v1/dashboard/bilateral/timeline'),
    staleTime: 1000 * 60 * 5, // 5 dk - timeline data changes infrequently
  });

  // Panel-specific bilateral data (refetched when slider moves)
  const panelBilateralQuery = useQuery({
    queryKey: ['bilateral-panel', selectedPanel?.file_id],
    queryFn: () =>
      selectedPanel
        ? apiClient.get<BilateralSentimentData[]>(
            `/api/v1/dashboard/bilateral?file_id=${selectedPanel.file_id}`,
          )
        : Promise.resolve(null),
    enabled: !!selectedPanel,
    staleTime: 1000 * 30, // 30 sn - interactive data needs fresher cache
  });

  const handleTimelineStep = useCallback((entry: PanelTimelineEntry | null) => {
    setSelectedPanel(entry);
  }, []);

  // Active bilateral data: panel-specific if slider is active, else aggregate
  const activeBilateral: BilateralSentimentData[] =
    selectedPanel && panelBilateralQuery.data
      ? panelBilateralQuery.data
      : (dashboardQuery.data?.bilateral ?? []);

  useEffect(() => {
    if (dashboardQuery.isError) {
      toast.error('Dashboard verileri yüklenemedi.');
    }
  }, [dashboardQuery.isError, toast]);

  if (dashboardQuery.isPending) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-28 shimmer" />
          ))}
        </div>
        <div className="h-80 shimmer" />
      </div>
    );
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <div className="border border-carbon-550 bg-carbon-900 p-6 text-sm text-carbon-300">
        <p className="font-semibold text-carbon-50">Dashboard verileri alınamadı.</p>
        <p className="mt-2 text-carbon-400">
          API bağlantısını ve auth token akışını kontrol edip yeniden deneyin.
        </p>
        <button
          type="button"
          onClick={() => dashboardQuery.refetch()}
          className="mt-4 btn-primary px-4 py-2 text-xs"
        >
          Tekrar Dene
        </button>
      </div>
    );
  }

  const { kpi, formulaHealth, dailyTrend, priorityDist, triggerDist, consensusDist } =
    dashboardQuery.data;

  const COLORS =
    theme === 'dark'
      ? ['#333333', '#505050', '#8A8A8A', '#E0E0E0']
      : ['#E0E0E0', '#ADB5BD', '#868E96', '#495057'];
  const CONSENSUS_COLORS =
    theme === 'dark'
      ? ['#264D26', '#5C4A26', '#5C2626', '#8A8A8A']
      : ['#2E7D32', '#EF6C00', '#C62828', '#868E96'];

  const highFpCount = formulaHealth?.filter((item) => item.false_positive_rate > 0.3).length || 0;

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('dashboard.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('dashboard.desc')}</p>
        </div>
      </div>

      {highFpCount > 0 && (
        <div className="flex items-center gap-2 p-4 bg-signal-fail/10 border border-hair border-signal-fail text-signal-fail text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>
            Dikkat: <strong>{highFpCount}</strong> formülde yüksek false positive oranı (%30 üzeri)
            saptandı. Detaylar için sayfa altındaki Formül Sağlık Tablosu'nu inceleyin.
          </span>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          title={t('dashboard.kpi.total_logs')}
          value={kpi?.total_logs.toLocaleString() || '0'}
          icon={<Activity className="w-4 h-4" />}
          accent="white"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.total_pass')}
          value={kpi?.total_pass.toLocaleString() || '0'}
          icon={<CheckCircle className="w-4 h-4" />}
          accent="pass"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.total_fail')}
          value={kpi?.total_fail.toLocaleString() || '0'}
          icon={<XCircle className="w-4 h-4" />}
          accent="fail"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.pending_review')}
          value={kpi?.pending_review.toLocaleString() || '0'}
          icon={<Clock className="w-4 h-4" />}
          accent="warn"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.confirmed_fail')}
          value={kpi?.confirmed_fail.toLocaleString() || '0'}
          icon={<AlertTriangle className="w-4 h-4" />}
          accent="fail"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.false_positive')}
          value={kpi?.confirmed_pass.toLocaleString() || '0'}
          icon={<ShieldCheck className="w-4 h-4" />}
          accent="muted"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.corrected')}
          value={kpi?.corrected.toLocaleString() || '0'}
          icon={<Edit3 className="w-4 h-4" />}
          accent="muted"
          monospace
        />
        <KpiCard
          title={t('dashboard.kpi.accuracy')}
          value={`%${kpi?.accuracy_percentage.toFixed(2)}`}
          icon={<TrendingUp className="w-4 h-4" />}
          accent="white"
          monospace
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-carbon-900 border border-hair border-carbon-550 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                {t('dashboard.chart.daily_trend')}
              </h3>
              <p className="text-micro text-carbon-400 mt-1">{t('dashboard.chart.last_30_days')}</p>
            </div>
            <BarChart3 className="w-4 h-4 text-carbon-400" />
          </div>
          <div className="h-64">
            {dailyTrend && dailyTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyTrend}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={theme === 'dark' ? '#2A2A2A' : '#E9ECEF'}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{
                      fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                    axisLine={{
                      stroke: theme === 'dark' ? '#2A2A2A' : '#E9ECEF',
                    }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{
                      fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === 'dark' ? '#161616' : '#FFFFFF',
                      border: theme === 'dark' ? '0.5px solid #2A2A2A' : '0.5px solid #CED4DA',
                      borderRadius: 0,
                      fontSize: 12,
                      fontFamily: 'JetBrains Mono',
                      color: theme === 'dark' ? '#F5F5F5' : '#1A1A1A',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pass_count"
                    stroke={theme === 'dark' ? '#264D26' : '#2E7D32'}
                    strokeWidth={1.5}
                    dot={false}
                    name="PASS"
                  />
                  <Line
                    type="monotone"
                    dataKey="fail_count"
                    stroke={theme === 'dark' ? '#5C2626' : '#C62828'}
                    strokeWidth={1.5}
                    dot={false}
                    name="FAIL"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
                <BarChart3 className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
                <span>Zaman serisi verisi bulunmamaktadır.</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                {t('dashboard.chart.triage_dist')}
              </h3>
              <p className="text-micro text-carbon-400 mt-1">
                {t('dashboard.chart.priority_levels')}
              </p>
            </div>
            <PieChart className="w-4 h-4 text-carbon-400" />
          </div>
          <div className="h-64">
            {priorityDist && priorityDist.some((p) => p.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <RePieChart>
                  <Pie
                    data={priorityDist}
                    dataKey="count"
                    nameKey="priority"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    stroke={theme === 'dark' ? '#0A0A0A' : '#FFFFFF'}
                    strokeWidth={2}
                  >
                    {priorityDist.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === 'dark' ? '#161616' : '#FFFFFF',
                      border: theme === 'dark' ? '0.5px solid #2A2A2A' : '0.5px solid #CED4DA',
                      borderRadius: 0,
                      fontSize: 12,
                      fontFamily: 'JetBrains Mono',
                      color: theme === 'dark' ? '#F5F5F5' : '#1A1A1A',
                    }}
                  />
                </RePieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
                <PieChart className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
                <span>Öncelik dağılım verisi bulunmamaktadır.</span>
              </div>
            )}
          </div>
          {priorityDist && priorityDist.some((p) => p.count > 0) && (
            <div className="mt-4 space-y-2">
              {priorityDist.map((p, i) => (
                <div key={p.priority} className="flex items-center justify-between text-2xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2" style={{ backgroundColor: COLORS[i] }} />
                    <span className="text-carbon-300">{p.priority}</span>
                  </div>
                  <span className="font-mono text-carbon-200">{p.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                {t('dashboard.chart.formula_health')}
              </h3>
              <p className="text-micro text-carbon-400 mt-1">
                {t('dashboard.chart.fp_correction_rates')}
              </p>
            </div>
            <Zap className="w-4 h-4 text-carbon-400" />
          </div>
          {formulaHealth && formulaHealth.length > 0 ? (
            <FormulaHealthChart data={formulaHealth} />
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
              <Zap className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
              <span>Formül sağlık verisi bulunmamaktadır.</span>
            </div>
          )}
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                {t('dashboard.chart.trigger_dist')}
              </h3>
              <p className="text-micro text-carbon-400 mt-1">
                {t('dashboard.chart.triage_reasons')}
              </p>
            </div>
            <AlertTriangle className="w-4 h-4 text-carbon-400" />
          </div>
          <div className="h-64">
            {triggerDist && triggerDist.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={triggerDist} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={theme === 'dark' ? '#2A2A2A' : '#E9ECEF'}
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{
                      fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="trigger"
                    tick={{
                      fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                    axisLine={false}
                    tickLine={false}
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === 'dark' ? '#161616' : '#FFFFFF',
                      border: theme === 'dark' ? '0.5px solid #2A2A2A' : '0.5px solid #CED4DA',
                      borderRadius: 0,
                      fontSize: 12,
                      fontFamily: 'JetBrains Mono',
                      color: theme === 'dark' ? '#F5F5F5' : '#1A1A1A',
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill={theme === 'dark' ? '#505050' : '#ADB5BD'}
                    stroke={theme === 'dark' ? '#2A2A2A' : '#CED4DA'}
                    strokeWidth={1}
                    barSize={14}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
                <AlertTriangle className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
                <span>Tetikleyici dağılım verisi bulunmamaktadır.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <FormulaHealthTable data={formulaHealth} />

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              {t('dashboard.chart.consensus_level_dist')}
            </h3>
            <p className="text-micro text-carbon-400 mt-1">
              {t('dashboard.chart.dualgate_outputs')}
            </p>
          </div>
        </div>
        <div className="h-48">
          {consensusDist && consensusDist.some((c) => c.count > 0) ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={consensusDist}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={theme === 'dark' ? '#2A2A2A' : '#E9ECEF'}
                  vertical={false}
                />
                <XAxis
                  dataKey="consensus"
                  tick={{
                    fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: theme === 'dark' ? '#2A2A2A' : '#E9ECEF' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{
                    fill: theme === 'dark' ? '#8A8A8A' : '#495057',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: theme === 'dark' ? '#161616' : '#FFFFFF',
                    border: theme === 'dark' ? '0.5px solid #2A2A2A' : '0.5px solid #CED4DA',
                    borderRadius: 0,
                    fontSize: 12,
                    fontFamily: 'JetBrains Mono',
                    color: theme === 'dark' ? '#F5F5F5' : '#1A1A1A',
                  }}
                />
                <Bar dataKey="count" strokeWidth={1} barSize={40}>
                  {consensusDist.map((_, i) => (
                    <Cell key={i} fill={CONSENSUS_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
              <BarChart3 className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
              <span>Konsensüs seviye verisi bulunmamaktadır.</span>
            </div>
          )}
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              {t('dashboard.chart.bilateral_heatmap')}
            </h3>
            <p className="text-micro text-carbon-400 mt-1">
              {t('dashboard.chart.bilateral_heatmap_desc')}
            </p>
          </div>
          <Globe className="w-4 h-4 text-carbon-400" />
        </div>
        {activeBilateral && activeBilateral.length > 0 ? (
          <BilateralHeatmap
            data={activeBilateral}
            timeline={timelineQuery.data ?? []}
            onTimelineStep={handleTimelineStep}
            playIntervalMs={2500}
          />
        ) : (
          <div className="h-96 flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40 font-mono text-xs">
            <Globe className="w-8 h-8 mb-2 text-carbon-500 opacity-60" />
            <span>İkili ilişkiler veri seti bulunmamaktadır.</span>
          </div>
        )}
      </div>
    </div>
  );
};
