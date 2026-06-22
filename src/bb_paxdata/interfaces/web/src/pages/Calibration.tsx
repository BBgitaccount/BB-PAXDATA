import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { DataTable } from '@/components/DataTable';
import {
  FormulaHealthTrendChart,
  type FormulaTrendData,
} from '@/components/FormulaHealthTrendChart';
import type { CalibrationReport, ReviewerPerformance } from '@/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  TrendingUp,
  Users,
  BarChart3,
} from 'lucide-react';
import { cn } from '@/utils/helpers';

export const Calibration = () => {
  const toast = useToast();
  const { t } = useTranslation();

  const reportQuery = useQuery({
    queryKey: ['calibration-report'],
    queryFn: () => apiClient.get<CalibrationReport>('/api/v1/dashboard/calibration'),
    staleTime: 1000 * 60 * 5, // 5 dk - calibration data changes infrequently
  });

  const performanceQuery = useQuery({
    queryKey: ['reviewer-performance'],
    queryFn: () => apiClient.get<ReviewerPerformance[]>('/api/v1/verdict/audit?group_by=reviewer'),
    staleTime: 1000 * 60 * 5, // 5 dk - performance data changes infrequently
  });

  const trendQuery = useQuery({
    queryKey: ['calibration-trend'],
    queryFn: () =>
      apiClient.get<{ month: string; kappa: number; f1: number }[]>(
        '/api/v1/dashboard/calibration/trend?months=6',
      ),
    staleTime: 1000 * 60 * 10, // 10 dk - historical trend data is stable
  });

  const formulaTrendQuery = useQuery({
    queryKey: ['formula-health-trend'],
    queryFn: () =>
      apiClient.get<FormulaTrendData[]>('/api/v1/dashboard/formulas/health/trend?days=30'),
    staleTime: 1000 * 60 * 10, // 10 dk - historical trend data is stable
  });

  useEffect(() => {
    if (reportQuery.isError || performanceQuery.isError) {
      toast.error('Kalibrasyon verileri yüklenemedi.');
    }
  }, [reportQuery.isError, performanceQuery.isError, toast]);

  const loading = reportQuery.isPending || performanceQuery.isPending || trendQuery.isPending;

  const report = reportQuery.data || null;
  const performance = performanceQuery.data || [];
  const trendData = trendQuery.data || [];
  const formulaTrend = formulaTrendQuery.data || [];

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 shimmer" />
          ))}
        </div>
        <div className="h-80 shimmer" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
          {t('calibration.title')}
        </h1>
        <p className="text-sm text-carbon-400 mt-1">{t('calibration.desc')}</p>
      </div>

      {report?.requires_prompt_update && (
        <div className="bg-carbon-900 border border-signal-fail p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-carbon-50" />
          <div>
            <span className="text-sm font-medium text-carbon-50">Prompt güncellenmeli!</span>
            <p className="text-2xs text-carbon-400 mt-0.5">{report.alert_message}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">Cohen's Kappa (Frame)</span>
            <Activity className="w-3.5 h-3.5 text-carbon-400" />
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report?.cohens_kappa_frame !== null && report?.cohens_kappa_frame !== undefined
              ? report.cohens_kappa_frame.toFixed(2)
              : '-'}
          </div>
          <div
            className={cn(
              'mt-2 text-micro',
              report &&
                report.cohens_kappa_frame !== null &&
                report.cohens_kappa_frame !== undefined &&
                report.cohens_kappa_frame > 0.67
                ? 'text-signal-pass'
                : 'text-signal-warn',
            )}
          >
            {report &&
            report.cohens_kappa_frame !== null &&
            report.cohens_kappa_frame !== undefined &&
            report.cohens_kappa_frame > 0.67
              ? 'Güvenilir'
              : 'Marjinal'}
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">Cohen's Kappa (Risk)</span>
            <Activity className="w-3.5 h-3.5 text-carbon-400" />
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report?.cohens_kappa_risk !== null && report?.cohens_kappa_risk !== undefined
              ? report.cohens_kappa_risk.toFixed(2)
              : '-'}
          </div>
          <div
            className={cn(
              'mt-2 text-micro',
              report &&
                report.cohens_kappa_risk !== null &&
                report.cohens_kappa_risk !== undefined &&
                report.cohens_kappa_risk > 0.67
                ? 'text-signal-pass'
                : 'text-signal-warn',
            )}
          >
            {report &&
            report.cohens_kappa_risk !== null &&
            report.cohens_kappa_risk !== undefined &&
            report.cohens_kappa_risk > 0.67
              ? 'Güvenilir'
              : 'Marjinal'}
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">F1 Score (Frame)</span>
            <TrendingUp className="w-3.5 h-3.5 text-carbon-400" />
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report?.ai_human_f1_frame !== null && report?.ai_human_f1_frame !== undefined
              ? report.ai_human_f1_frame.toFixed(2)
              : '-'}
          </div>
          <div className="mt-2 w-full bg-carbon-800 h-1">
            <div
              className="bg-carbon-400 h-1"
              style={{ width: `${(report?.ai_human_f1_frame || 0) * 100}%` }}
            />
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">F1 Score (Risk)</span>
            <TrendingUp className="w-3.5 h-3.5 text-carbon-400" />
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report?.ai_human_f1_risk !== null && report?.ai_human_f1_risk !== undefined
              ? report.ai_human_f1_risk.toFixed(2)
              : '-'}
          </div>
          <div className="mt-2 w-full bg-carbon-800 h-1">
            <div
              className="bg-carbon-400 h-1"
              style={{ width: `${(report?.ai_human_f1_risk || 0) * 100}%` }}
            />
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">SBI MAE</span>
            <BarChart3 className="w-3.5 h-3.5 text-carbon-400" />
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report?.sbi_mae !== null && report?.sbi_mae !== undefined
              ? report.sbi_mae.toFixed(1)
              : '-'}
          </div>
          <div className="mt-2 text-micro text-carbon-400">Düşük = iyi</div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="label-micro">Güvenilirlik</span>
            {report?.is_reliable ? (
              <CheckCircle className="w-4 h-4 text-signal-pass" />
            ) : (
              <XCircle className="w-4 h-4 text-signal-fail" />
            )}
          </div>
          <div className="text-2xl font-semibold font-mono text-carbon-50">
            {report == null ? '-' : report.is_reliable ? 'EVET' : 'HAYIR'}
          </div>
          <div className="mt-2 text-micro text-carbon-400">
            {report?.disagreement_rate !== null && report?.disagreement_rate !== undefined
              ? `${report.disagreement_rate.toFixed(1)}%`
              : '0%'}{' '}
            anlaşmazlık
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <h3 className="text-sm font-semibold text-carbon-50 tracking-tight mb-4">
            AI-İnsan Agreement Trend
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{
                    fill: '#8A8A8A',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: '#2A2A2A' }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{
                    fill: '#8A8A8A',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#161616',
                    border: '0.5px solid #2A2A2A',
                    fontSize: 12,
                    fontFamily: 'JetBrains Mono',
                    color: '#F5F5F5',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="kappa"
                  stroke="#E0E0E0"
                  strokeWidth={1.5}
                  dot={false}
                  name="Kappa"
                />
                <Line
                  type="monotone"
                  dataKey="f1"
                  stroke="#505050"
                  strokeWidth={1.5}
                  dot={false}
                  name="F1"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <h3 className="text-sm font-semibold text-carbon-50 tracking-tight mb-4">
            Reviewer Throughput
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={performance}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
                <XAxis
                  dataKey="reviewer_id"
                  tick={{
                    fill: '#8A8A8A',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: '#2A2A2A' }}
                  tickLine={false}
                  angle={-30}
                  textAnchor="end"
                  height={50}
                />
                <YAxis
                  tick={{
                    fill: '#8A8A8A',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#161616',
                    border: '0.5px solid #2A2A2A',
                    fontSize: 12,
                    fontFamily: 'JetBrains Mono',
                    color: '#F5F5F5',
                  }}
                />
                <Bar
                  dataKey="total_actions"
                  fill="#505050"
                  stroke="#2A2A2A"
                  strokeWidth={1}
                  barSize={24}
                />
                <Bar
                  dataKey="verdict_count"
                  fill="#8A8A8A"
                  stroke="#2A2A2A"
                  strokeWidth={1}
                  barSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <h3 className="text-sm font-semibold text-carbon-50 tracking-tight mb-4">
          Anlaşmazlık Pattern'leri
        </h3>
        <div className="space-y-2">
          {report?.top_disagreement_patterns?.length ? (
            report.top_disagreement_patterns.map((pattern, i) => (
              <div
                key={i}
                className="flex items-center gap-3 py-2 border-b border-hair border-carbon-550/50"
              >
                <span className="font-mono text-micro text-carbon-500">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="text-sm text-carbon-200">{pattern}</span>
              </div>
            ))
          ) : (
            <div className="py-4 text-center text-xs text-carbon-500 font-mono">
              Anlaşmazlık pattern verisi bulunmamaktadır.
            </div>
          )}
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <Users className="w-4 h-4 text-carbon-400" />
          <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Reviewer Performans
          </h3>
        </div>
        <DataTable
          columns={[
            {
              key: 'id',
              header: 'Reviewer ID',
              width: '220px',
              render: (r) => <span className="text-2xs text-carbon-200">{r.reviewer_id}</span>,
            },
            {
              key: 'total',
              header: 'Toplam İşlem',
              width: '120px',
              render: (r) => (
                <span className="font-mono text-2xs text-carbon-200">{r.total_actions}</span>
              ),
            },
            {
              key: 'verdict',
              header: 'Karar',
              width: '100px',
              render: (r) => (
                <span className="font-mono text-2xs text-carbon-200">{r.verdict_count}</span>
              ),
            },
            {
              key: 'correction',
              header: 'Düzeltme',
              width: '100px',
              render: (r) => (
                <span className="font-mono text-2xs text-carbon-200">{r.correction_count}</span>
              ),
            },
            {
              key: 'rate',
              header: 'Oran %',
              width: '100px',
              render: (r) => (
                <span className="font-mono text-2xs text-carbon-200">
                  {r.correction_rate.toFixed(1)}%
                </span>
              ),
            },
          ]}
          data={performance}
          keyExtractor={(r) => r.reviewer_id}
        />
      </div>

      {/* ── Formula FP Trend ───────────────────────────────────────── */}
      <FormulaHealthTrendChart data={formulaTrend} />
    </div>
  );
};
