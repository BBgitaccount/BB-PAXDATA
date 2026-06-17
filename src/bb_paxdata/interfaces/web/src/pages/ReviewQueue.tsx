import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient, ApiError } from '@/services/apiClient';
import { DataTable } from '@/components/DataTable';
import { PriorityBadge } from '@/components/PriorityBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { useToast } from '@/hooks/useToast';
import { formatDate, truncate } from '@/utils/helpers';
import type { FailQueueItem, FormulaName, TriagePriority } from '@/types';
import { Filter, Search, Eye, ShieldOff } from 'lucide-react';
import { cn } from '@/utils/helpers';
import { useReviewQueueStore } from '@/store/reviewQueueStore';
import { UncertaintyBadge } from '@/components/UncertaintyBadge';
import { useTranslation } from '@/hooks/useTranslation';

const formulas: FormulaName[] = [
  'vader_compound',
  'negation_aware_diplo',
  'emotion_category_alignment',
  'hedging_score',
  'politeness_ratio',
  'sbi_score',
  'dki_score',
  'risk_score',
];

export const ReviewQueue = ({ mode = 'logic' }: { mode?: 'logic' | 'ai' }) => {
  const [filters, setFilters] = useState({
    formula: '',
    status: 'unreviewed' as 'unreviewed' | 'reviewed' | 'all',
    priority: [] as TriagePriority[],
    search: '',
  });
  const toast = useToast();
  const navigate = useNavigate();
  const hiddenLogIds = useReviewQueueStore((state) => state.hiddenLogIds);
  const { t } = useTranslation();

  const queueQuery = useQuery({
    queryKey: ['fail-queue', filters.formula, filters.status],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.formula) {
        params.set('formula_name', filters.formula);
      }
      params.set('status_filter', filters.status);
      params.set('limit', '50');

      return apiClient.get<FailQueueItem[]>(`/api/v1/queue?${params.toString()}`);
    },
  });

  useEffect(() => {
    if (queueQuery.isError) {
      const err = queueQuery.error;
      // 401 is handled globally by authStore (auto-logout + redirect).
      // Only show toast for non-401 errors to avoid duplicate noise.
      if (!(err instanceof ApiError && err.status === 401)) {
        toast.error('Kuyruk verileri yüklenemedi.');
      }
    }
  }, [queueQuery.isError, queueQuery.error, toast]);

  const data = queueQuery.data ?? [];
  const visibleData = data.filter((item) => {
    if (!item) return false;
    const itemLogId = Number(item.log_id);
    return !hiddenLogIds.some((id) => Number(id) === itemLogId);
  });

  const filtered = visibleData.filter((item) => {
    if (!item) return false;
    if (filters.search) {
      const searchText = filters.search.toLowerCase();
      const sentenceText = (item.sentence_text || '').toLowerCase();
      const sentId = (item.sent_id || '').toLowerCase();
      const speakerName = (item.speaker_name || '').toLowerCase();
      const matchesSearch =
        sentenceText.includes(searchText) ||
        sentId.includes(searchText) ||
        speakerName.includes(searchText);
      if (!matchesSearch) return false;
    }
    return true;
  });

  const columns = [
    {
      key: 'priority',
      header: 'Öncelik',
      width: '90px',
      render: (r: FailQueueItem) => (
        <PriorityBadge
          priority={
            r.trigger_type === 'CRITICAL_ANOMALY'
              ? 'CRITICAL'
              : r.priority_score > 75
                ? 'HIGH_PRIORITY'
                : 'NORMAL'
          }
        />
      ),
    },
    {
      key: 'sent_id',
      header: 'Sent ID',
      width: '110px',
      render: (r: FailQueueItem) => (
        <span className="font-mono text-2xs text-carbon-300">{r.sent_id}</span>
      ),
    },
    {
      key: 'sentence',
      header: 'Cümle Metni',
      render: (r: FailQueueItem) => (
        <div className="group relative">
          <span className="text-sm text-carbon-200">{truncate(r.sentence_text, 90)}</span>
          <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50 bg-carbon-900 border border-hair border-carbon-550 p-3 max-w-md shadow-elevated">
            <p className="text-xs text-carbon-200 leading-relaxed">{r.sentence_text}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'speaker',
      header: 'Konuşmacı',
      width: '120px',
      render: (r: FailQueueItem) => (
        <span className="text-2xs text-carbon-300">{r.speaker_name}</span>
      ),
    },
    {
      key: 'country',
      header: 'Ülke',
      width: '100px',
      render: (r: FailQueueItem) => <span className="text-2xs text-carbon-300">{r.country}</span>,
    },
    {
      key: 'power',
      header: 'Güç',
      width: '60px',
      render: (r: FailQueueItem) => (
        <span className="font-mono text-2xs text-carbon-300">{r.power_level}</span>
      ),
    },
    {
      key: 'formula',
      header: 'Formül',
      width: '140px',
      render: (r: FailQueueItem) => (
        <span className="font-mono text-2xs text-carbon-300">{r.formula_name}</span>
      ),
    },
    {
      key: 'expected',
      header: 'Beklenen',
      width: '100px',
      render: (r: FailQueueItem) => (
        <span className="font-mono text-2xs text-carbon-400">{r.expected_constraint}</span>
      ),
    },
    {
      key: 'actual',
      header: 'Gerçek',
      width: '80px',
      render: (r: FailQueueItem) => {
        const val =
          typeof r.actual_value === 'number'
            ? r.actual_value.toFixed(3)
            : r.actual_value !== null && r.actual_value !== undefined
              ? String(r.actual_value)
              : '';
        return <span className="font-mono text-2xs text-carbon-200">{val}</span>;
      },
    },
    ...(mode === 'ai'
      ? [
          {
            key: 'ai_risk',
            header: 'AI Risk',
            width: '70px',
            render: (r: FailQueueItem) => (
              <span className="font-mono text-2xs text-carbon-200">{r.ai_risk_score}</span>
            ),
          },
          {
            key: 'ai_confidence',
            header: 'Güven',
            width: '130px',
            render: (r: FailQueueItem) => (
              <UncertaintyBadge
                score={(r as any).ai_confidence}
                status={(r as any).uncertainty_status}
              />
            ),
          },
        ]
      : []),
    {
      key: 'status',
      header: 'Durum',
      width: '100px',
      render: (r: FailQueueItem) => <StatusBadge status={r.review_status || 'PENDING'} />,
    },
    ...(mode === 'ai'
      ? [
          {
            key: 'trigger',
            header: 'Trigger',
            width: '110px',
            render: (r: FailQueueItem) => (
              <span className="font-mono text-micro text-carbon-400">{r.trigger_type}</span>
            ),
          },
        ]
      : []),
    {
      key: 'date',
      header: 'Tarih',
      width: '120px',
      render: (r: FailQueueItem) => (
        <span className="text-2xs text-carbon-400">{formatDate(r.created_at)}</span>
      ),
    },
    {
      key: 'action',
      header: '',
      width: '80px',
      render: (r: FailQueueItem) => (
        <button
          onClick={() =>
            navigate(`/hitl-${mode}/queue/${r.log_id}`, {
              state: {
                sent_id: r.sent_id,
                formula_name: r.formula_name,
                mode,
                item: r,
              },
            })
          }
          className="flex items-center gap-1.5 px-3 py-1.5 bg-carbon-50 text-carbon-950 text-micro font-medium tracking-diplomatic hover:bg-carbon-200 transition-colors"
        >
          <Eye className="w-3 h-3" />
          İNCELE
        </button>
      ),
    },
  ];

  // ─── 401 Guard: render inline access denied instead of crashing ──────────────
  const is401 =
    queueQuery.isError && queueQuery.error instanceof ApiError && queueQuery.error.status === 401;

  if (is401) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4 text-center animate-[fade-in-up_300ms_ease-out_both]">
        <div className="w-12 h-12 rounded-full bg-signal-fail/15 flex items-center justify-center">
          <ShieldOff className="w-6 h-6 text-signal-fail" />
        </div>
        <div>
          <p className="text-sm font-semibold text-carbon-100 uppercase tracking-widest">
            Erişim Yetkisi Yok
          </p>
          <p className="text-2xs text-carbon-400 mt-1">
            Bu kuyruğu görüntülemek için yetkiniz yetersiz. Lütfen yöneticinizle iletişime geçin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {mode === 'logic' ? t('queue.logic_title') : t('queue.ai_title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">
            {mode === 'logic' ? t('queue.logic_desc') : t('queue.ai_desc')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-micro font-mono text-carbon-400">
            {t('queue.records_count').replace('{count}', filtered.length.toString())}
          </span>
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-carbon-400" />
            <select
              value={filters.formula}
              onChange={(e) => setFilters({ ...filters, formula: e.target.value })}
              className="bg-carbon-900 border border-hair border-carbon-550 text-xs text-carbon-200 px-3 py-2 min-w-[180px]"
            >
              <option value="">Tüm Formüller</option>
              {formulas.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1 bg-carbon-800 border border-hair border-carbon-550 p-0.5">
            {(['unreviewed', 'reviewed', 'all'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilters({ ...filters, status: s })}
                className={cn(
                  'px-3 py-1.5 text-micro font-medium tracking-diplomatic transition-colors',
                  filters.status === s
                    ? 'bg-carbon-700 text-carbon-50'
                    : 'text-carbon-400 hover:text-carbon-200',
                )}
              >
                {s === 'unreviewed' ? 'BEKLEYEN' : s === 'reviewed' ? 'İNCELENDİ' : 'TÜMÜ'}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-carbon-400" />
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="sent_id, konuşmacı..."
              className="bg-carbon-900 border border-hair border-carbon-550 text-xs text-carbon-200 px-3 py-2 w-48"
            />
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyExtractor={(r) => r.log_id.toString()}
        loading={queueQuery.isPending}
      />
    </div>
  );
};
