import { DataTable } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { TripletView } from '@/components/TripletView';
import { UncertaintyBadge } from '@/components/UncertaintyBadge';
import { VerdictForm } from '@/components/VerdictForm';
import { GOLD_STANDARDS } from '@/constants/goldStandards';
import { useToast } from '@/hooks/useToast';
import { apiClient } from '@/services/apiClient';
import type { ComparisonRow, FailQueueItem, SimilarCase, TripletContext } from '@/types';
import { cn, truncate } from '@/utils/helpers';
import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  Cpu,
  FileText,
  GitCompare,
  TableProperties,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

export const ReviewDetail = () => {
  const { logId } = useParams<{ logId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const mode = location.pathname.includes('/hitl-ai/') ? 'ai' : 'logic';
  const state = location.state as {
    sent_id?: string;
    formula_name?: string;
    mode?: 'logic' | 'ai';
    item?: FailQueueItem;
  } | null;
  const sentId = state?.sent_id;
  const formulaName = state?.formula_name;

  const tripletQuery = useQuery({
    queryKey: ['review-triplet', logId, sentId],
    queryFn: async () => {
      if (sentId) {
        return apiClient.get<TripletContext>(`/api/v1/queue/context/${sentId}`);
      }
      return apiClient.get<TripletContext>(`/api/v1/queue/context/by-log-id/${logId}`);
    },
    enabled: Boolean(logId),
    staleTime: 1000 * 60 * 10, // 10 dk - context data for specific log is stable
  });

  const similarQuery = useQuery({
    queryKey: ['review-similar', logId, sentId, formulaName],
    queryFn: async () => {
      if (sentId && formulaName) {
        return apiClient.get<SimilarCase[]>(`/api/v1/queue/similar/${sentId}/${formulaName}`);
      }
      return apiClient.get<SimilarCase[]>(`/api/v1/queue/similar/by-log-id/${logId}`);
    },
    enabled: Boolean(logId),
    staleTime: 1000 * 60 * 10, // 10 dk - similar cases data is stable
  });

  const logItemQuery = useQuery({
    queryKey: ['queue-item', logId],
    queryFn: async () => {
      try {
        return await apiClient.get<FailQueueItem>(`/api/v1/queue/log/${logId}`);
      } catch (err) {
        console.error('Failed to get log item by id, falling back to queue list search', err);
        const list = await apiClient.get<FailQueueItem[]>(
          '/api/v1/queue?status_filter=all&limit=50',
        );
        const found = list.find((item) => item.log_id === Number(logId));
        if (found) return found;
        throw err;
      }
    },
    enabled: Boolean(logId),
    staleTime: 1000 * 60 * 10, // 10 dk - log item data is stable
  });

  useEffect(() => {
    if (tripletQuery.isError || similarQuery.isError) {
      toast.error('Detay verileri yüklenemedi.');
    }
  }, [similarQuery.isError, toast, tripletQuery.isError]);

  useEffect(() => {
    if (!logId || isNaN(Number(logId))) {
      toast.error('Geçersiz Log ID.');
      navigate(mode === 'logic' ? '/hitl-logic/queue' : '/hitl-ai/queue', {
        replace: true,
      });
    }
  }, [logId, navigate, mode, toast]);

  useEffect(() => {
    if (logItemQuery.isError) {
      toast.error('Vaka detayları yüklenemedi veya bulunamadı.');
      navigate(mode === 'logic' ? '/hitl-logic/queue' : '/hitl-ai/queue', {
        replace: true,
      });
    }
  }, [logItemQuery.isError, navigate, mode, toast]);

  useEffect(() => {
    if (logItemQuery.isSuccess && !logItemQuery.data && !state?.item) {
      toast.error('Vaka bulunamadı.');
      navigate(mode === 'logic' ? '/hitl-logic/queue' : '/hitl-ai/queue', {
        replace: true,
      });
    }
  }, [logItemQuery.isSuccess, logItemQuery.data, state?.item, navigate, mode, toast]);

  const triplet = tripletQuery.data ?? null;
  const similar = similarQuery.data ?? [];
  const item = state?.item ?? logItemQuery.data ?? null;

  const queueListQuery = useQuery({
    queryKey: ['fail-queue-list-for-formulas'],
    queryFn: () => apiClient.get<FailQueueItem[]>('/api/v1/queue?status_filter=all&limit=100'),
    staleTime: 1000 * 60 * 2, // 2 dk - queue list changes frequently
  });

  const sameSentenceFormulaLogs = (queueListQuery.data ?? []).filter(
    (q) => item && q.sent_id === item.sent_id,
  );

  const comparisonQuery = useQuery({
    queryKey: ['session-comparison', item?.file_id],
    queryFn: async () => {
      if (!item?.file_id) return null;
      try {
        const { session_ids } = await apiClient.get<{ session_ids: string[] }>(
          '/api/v1/compare/sessions/available',
        );
        const otherSession = session_ids.find((id) => id !== item.file_id) || item.file_id;

        return await apiClient.post<Record<string, unknown>>('/api/v1/compare/sessions', {
          session_a_id: otherSession,
          session_b_id: item.file_id,
          sbi_threshold: 5.0,
          dki_threshold: 0.1,
          risk_threshold: 10.0,
          hedging_threshold: 0.05,
          include_narrative: false,
        });
      } catch (err) {
        console.error('Failed to fetch session comparison', err);
        return null;
      }
    },
    enabled: !!item?.file_id,
    staleTime: 1000 * 60 * 10, // 10 dk - comparison data is stable
  });

  const getComparisonRows = (
    itemVal: FailQueueItem | null,
    compData: Record<string, unknown> | null,
  ): ComparisonRow[] => {
    if (!itemVal) return [];

    const rows: ComparisonRow[] = [];

    if (mode === 'ai' && compData?.success && compData.analysis_delta) {
      const delta = compData.analysis_delta;
      rows.push({
        metric: 'Risk Score (Session)',
        formula_value: '-',
        ai_value: '-',
        delta:
          delta.delta_risk !== null &&
          delta.delta_risk !== undefined &&
          typeof delta.delta_risk === 'number'
            ? delta.delta_risk.toFixed(2)
            : '0.00',
        aligned: !delta.delta_risk_significant,
      });
      rows.push({
        metric: 'Most Drifted Speaker',
        formula_value: '-',
        ai_value: delta.most_drifted_speaker || 'None',
        delta: '-',
        aligned: true,
      });
      rows.push({
        metric: 'Most Drifted Dim',
        formula_value: '-',
        ai_value: delta.most_drifted_dimension || 'None',
        delta: '-',
        aligned: true,
      });
      rows.push({
        metric: 'Sig. Changes Count',
        formula_value: '0',
        ai_value: String(delta.total_significant_changes || 0),
        delta: '-',
        aligned: (delta.total_significant_changes || 0) === 0,
      });
      return rows;
    }

    // 1. Sentiment/Tone Row
    const sentimentFormula =
      itemVal.formula_name === 'vader_compound'
        ? typeof itemVal.actual_value === 'number'
          ? itemVal.actual_value.toFixed(3)
          : String(itemVal.actual_value || '-')
        : itemVal.formula_name === 'negation_aware_diplo'
          ? typeof itemVal.actual_value === 'number'
            ? itemVal.actual_value.toFixed(3)
            : String(itemVal.actual_value || '-')
          : '-';
    const sentimentAI = itemVal.ai_diplomatic_tone || '-';
    rows.push({
      metric: 'Sentiment / Tone',
      formula_value: sentimentFormula,
      ai_value: sentimentAI,
      delta: itemVal.formula_name === 'vader_compound' ? 'N/A' : '-',
      aligned: itemVal.formula_name === 'vader_compound' ? itemVal.status === 'PASS' : true,
    });

    // 2. Emotion Row
    const emotionFormula =
      itemVal.formula_name === 'emotion_category_alignment'
        ? (itemVal.details?.actual_category as string) || '-'
        : '-';
    const emotionAI = itemVal.ai_emotion_category || '-';
    rows.push({
      metric: 'Emotion',
      formula_value: emotionFormula,
      ai_value: emotionAI,
      delta:
        itemVal.formula_name === 'emotion_category_alignment'
          ? emotionFormula === emotionAI
            ? 'Eşleşiyor'
            : 'Uyumsuz'
          : '-',
      aligned:
        itemVal.formula_name === 'emotion_category_alignment' ? itemVal.status === 'PASS' : true,
    });

    // 3. Risk Row
    const riskFormula =
      itemVal.formula_name === 'risk_score'
        ? itemVal.actual_value
        : itemVal.details?.avg_risk
          ? Number(itemVal.details.avg_risk)
          : '-';
    const riskAI =
      itemVal.ai_risk_score !== null && itemVal.ai_risk_score !== undefined
        ? itemVal.ai_risk_score
        : '-';
    let riskDelta = '-';
    if (typeof riskFormula === 'number' && typeof riskAI === 'number') {
      const diff = riskAI - riskFormula;
      riskDelta = diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);
    }
    rows.push({
      metric: 'Risk Score',
      formula_value: typeof riskFormula === 'number' ? riskFormula.toFixed(1) : riskFormula,
      ai_value: typeof riskAI === 'number' ? riskAI.toFixed(1) : riskAI,
      delta: riskDelta,
      aligned: itemVal.formula_name === 'risk_score' ? itemVal.status === 'PASS' : true,
    });

    // 4. Hedging Row
    const hedgingFormula =
      itemVal.formula_name === 'hedging_score'
        ? typeof itemVal.actual_value === 'number'
          ? itemVal.actual_value.toFixed(3)
          : String(itemVal.actual_value || '-')
        : '-';
    const hedgingAIScore = itemVal.details?.ai_hedging_score;
    const hedgingAI =
      hedgingAIScore !== undefined && hedgingAIScore !== null && !isNaN(Number(hedgingAIScore))
        ? Number(hedgingAIScore).toFixed(3)
        : '-';
    rows.push({
      metric: 'Hedging',
      formula_value: hedgingFormula,
      ai_value: hedgingAI,
      delta: itemVal.formula_name === 'hedging_score' ? 'N/A' : '-',
      aligned: itemVal.formula_name === 'hedging_score' ? itemVal.status === 'PASS' : true,
    });

    // 5. Politeness Row
    const politenessFormula =
      itemVal.formula_name === 'politeness_ratio'
        ? typeof itemVal.actual_value === 'number'
          ? itemVal.actual_value.toFixed(3)
          : String(itemVal.actual_value || '-')
        : '-';
    const politenessAIScore = itemVal.details?.ai_politeness_score;
    const politenessAI =
      politenessAIScore !== undefined &&
      politenessAIScore !== null &&
      !isNaN(Number(politenessAIScore))
        ? Number(politenessAIScore).toFixed(3)
        : '-';
    rows.push({
      metric: 'Politeness',
      formula_value: politenessFormula,
      ai_value: politenessAI,
      delta: itemVal.formula_name === 'politeness_ratio' ? 'N/A' : '-',
      aligned: itemVal.formula_name === 'politeness_ratio' ? itemVal.status === 'PASS' : true,
    });

    return rows;
  };

  const comparison = getComparisonRows(item, comparisonQuery.data);

  if (
    tripletQuery.isPending ||
    similarQuery.isPending ||
    logItemQuery.isPending ||
    (mode === 'ai' && comparisonQuery.isPending)
  ) {
    return (
      <div className="space-y-6">
        <div className="h-8 shimmer w-48" />
        <div className={cn('grid gap-6', mode === 'logic' ? 'grid-cols-2' : 'grid-cols-3')}>
          <div className="h-96 shimmer" />
          {mode === 'ai' && <div className="h-96 shimmer" />}
          <div className="h-96 shimmer" />
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="flex items-center justify-center p-8 bg-carbon-900 min-h-[50vh]">
        <span className="text-sm text-carbon-400">Yükleniyor...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(mode === 'logic' ? '/hitl-logic/queue' : '/hitl-ai/queue')}
          className="flex items-center gap-2 text-carbon-400 hover:text-carbon-50 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Kuyruğa Dön</span>
        </button>
        <div className="h-4 w-px bg-carbon-550" />
        <h1 className="text-sm font-semibold text-carbon-50 tracking-tight">
          {mode === 'logic' ? 'Formül Karar Formu' : 'AI Karar Formu'}
        </h1>
        <div className="h-4 w-px bg-carbon-550" />
        <span className="text-micro font-mono text-carbon-400">LOG-ID: {logId}</span>
        {mode === 'ai' && triplet && (
          <UncertaintyBadge
            score={(triplet as { ai_confidence?: number }).ai_confidence}
            status={(triplet as { uncertainty_status?: string }).uncertainty_status}
          />
        )}
      </div>
      <div className={cn('grid gap-6', mode === 'logic' ? 'grid-cols-2' : 'grid-cols-3')}>
        {/* Column 1: Context + Formula details + AI Analysis */}
        <div className="col-span-1 space-y-6">
          <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
            <div className="flex items-center gap-2 mb-6">
              <FileText className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
              <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">Bağlam</h2>
            </div>
            {triplet && <TripletView context={triplet} />}
          </div>

          {/* Formül Detayı */}
          <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
              <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                Formül Detayı: <span className="font-mono text-xs">{item.formula_name}</span>
              </h2>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="border border-hair border-carbon-550/50 p-2 bg-carbon-950">
                <span className="text-micro text-carbon-500 block">Beklenen</span>
                <span className="text-xs font-mono font-semibold text-carbon-200">
                  {item.expected_constraint}
                </span>
              </div>
              <div className="border border-hair border-carbon-550/50 p-2 bg-carbon-950">
                <span className="text-micro text-carbon-500 block">Gerçekleşen</span>
                <span className="text-xs font-mono font-semibold text-carbon-200">
                  {typeof item.actual_value === 'number'
                    ? item.actual_value.toFixed(4)
                    : String(item.actual_value || '0')}
                </span>
              </div>
              <div className="border border-hair border-carbon-550/50 p-2 bg-carbon-950">
                <span className="text-micro text-carbon-500 block">Delta</span>
                <span className="text-xs font-mono font-semibold text-carbon-200">
                  {(() => {
                    try {
                      const cleanExp = String(item.expected_constraint)
                        .split('==')
                        .pop()
                        ?.trim()
                        .split(' ')[0];
                      if (
                        cleanExp &&
                        !isNaN(Number(cleanExp)) &&
                        typeof item.actual_value === 'number'
                      ) {
                        const delta = item.actual_value - parseFloat(cleanExp);
                        return delta >= 0 ? `+${delta.toFixed(4)}` : delta.toFixed(4);
                      }
                    } catch {
                      // Ignore parsing error
                    }
                    return '—';
                  })()}
                </span>
              </div>
            </div>

            {item.details && Object.keys(item.details).length > 0 && (
              <div className="space-y-2">
                <span className="label-micro">📋 Hesaplama Detayları</span>
                <div className="border border-hair border-carbon-550/50 bg-carbon-950 p-3 max-h-[150px] overflow-y-auto font-mono text-2xs text-carbon-300 space-y-1">
                  {Object.entries(item.details).map(([k, v]) => (
                    <div
                      key={k}
                      className="flex justify-between py-1 border-b border-hair border-carbon-550/30 last:border-b-0"
                    >
                      <span className="text-carbon-400 font-semibold">{k}:</span>
                      <span className="text-carbon-200">
                        {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* AI Analizi */}
          <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Cpu className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
              <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">🤖 AI Analizi</h2>
            </div>

            {item.ai_risk_score !== null && item.ai_risk_score !== undefined ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-carbon-400">Risk Skoru:</span>
                  <span
                    className={cn(
                      'font-mono font-semibold',
                      item.ai_risk_score >= 7
                        ? 'text-signal-fail'
                        : item.ai_risk_score >= 4
                          ? 'text-signal-warn'
                          : 'text-signal-pass',
                    )}
                  >
                    {item.ai_risk_score}/10
                  </span>
                </div>
                <div className="w-full bg-carbon-800 h-1.5 rounded-micro overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-micro',
                      item.ai_risk_score >= 7
                        ? 'bg-signal-fail'
                        : item.ai_risk_score >= 4
                          ? 'bg-signal-warn'
                          : 'bg-signal-pass',
                    )}
                    style={{ width: `${item.ai_risk_score * 10}%` }}
                  />
                </div>
              </div>
            ) : (
              <div className="text-2xs text-carbon-500">Risk skoru mevcut değil</div>
            )}

            {item.ai_emotion_category && (
              <div className="flex justify-between items-center py-2 border-t border-hair border-carbon-550/30 text-xs">
                <span className="text-carbon-400">Duygu Kategorisi:</span>
                <span className="text-carbon-200 font-mono">{item.ai_emotion_category}</span>
              </div>
            )}

            {item.ai_diplomatic_tone && (
              <div className="flex justify-between items-center py-2 border-t border-hair border-carbon-550/30 text-xs">
                <span className="text-carbon-400">Diplomatik Ton:</span>
                <span className="text-carbon-200 font-mono">{item.ai_diplomatic_tone}</span>
              </div>
            )}
          </div>
        </div>

        {/* Column 2: AI vs Formül Comparison (only for AI mode) OR Verdict Form + Reference Examples (for logic mode) */}
        {mode === 'ai' ? (
          <div className="col-span-1 space-y-6">
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
              <div className="flex items-center gap-2 mb-6">
                <GitCompare className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                  AI vs Formül
                </h2>
              </div>
              <div className="space-y-0">
                {comparison.map((row, i) => (
                  <div
                    key={row.metric}
                    className={cn(
                      'flex items-center justify-between py-3 border-b border-hair border-carbon-550/50',
                      i === 0 && 'border-t',
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-carbon-300 font-medium w-24">{row.metric}</span>
                      {row.aligned ? (
                        <CheckCircle className="w-3 h-3 text-signal-pass" />
                      ) : (
                        <XCircle className="w-3 h-3 text-signal-fail" />
                      )}
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span className="text-micro text-carbon-500 block">Formül</span>
                        <span className="text-xs font-mono text-carbon-300">
                          {row.formula_value}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-micro text-carbon-500 block">AI</span>
                        <span className="text-xs font-mono text-carbon-200">{row.ai_value}</span>
                      </div>
                      <div className="text-right w-16">
                        <span
                          className={cn(
                            'text-xs font-mono',
                            String(row.delta).startsWith('+')
                              ? 'text-carbon-300'
                              : String(row.delta).startsWith('-')
                                ? 'text-carbon-400'
                                : 'text-carbon-500',
                          )}
                        >
                          {row.delta}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Tüm Formül Durumları (inside middle column in AI mode) */}
            {sameSentenceFormulaLogs.length > 0 && (
              <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4 animate-[fade-in-up_200ms_ease-out]">
                <div className="flex items-center gap-2 mb-2">
                  <TableProperties className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                  <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                    📋 Tüm Formül Durumları
                  </h2>
                </div>
                <div className="space-y-2">
                  {sameSentenceFormulaLogs.map((log) => {
                    const verdict = log.human_verdict;
                    const displayStatus = verdict || log.status;

                    return (
                      <div
                        key={log.log_id}
                        className="flex items-center justify-between text-xs py-1 border-b border-hair border-carbon-550/30 last:border-b-0"
                      >
                        <span className="font-mono text-carbon-300">{log.formula_name}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-2xs text-carbon-400">
                            {typeof log.actual_value === 'number'
                              ? log.actual_value.toFixed(3)
                              : String(log.actual_value)}
                          </span>
                          <StatusBadge status={displayStatus as HumanVerdict} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="col-span-1 space-y-6">
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
              <div className="flex items-center gap-2 mb-6">
                <AlertCircle className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">Karar Formu</h2>
              </div>
              <VerdictForm
                logId={Number(logId)}
                onSubmitted={() => toast.success('İnceleme tamamlandı.')}
              />
            </div>

            {/* Tüm Formül Durumları (inside right column in logic mode) */}
            {sameSentenceFormulaLogs.length > 0 && (
              <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4 animate-[fade-in-up_200ms_ease-out]">
                <div className="flex items-center gap-2 mb-2">
                  <TableProperties className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                  <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                    📋 Tüm Formül Durumları
                  </h2>
                </div>
                <div className="space-y-2">
                  {sameSentenceFormulaLogs.map((log) => {
                    const verdict = log.human_verdict;
                    const displayStatus = verdict || log.status;

                    return (
                      <div
                        key={log.log_id}
                        className="flex items-center justify-between text-xs py-1 border-b border-hair border-carbon-550/30 last:border-b-0"
                      >
                        <span className="font-mono text-carbon-300">{log.formula_name}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-2xs text-carbon-400">
                            {typeof log.actual_value === 'number'
                              ? log.actual_value.toFixed(3)
                              : String(log.actual_value)}
                          </span>
                          <StatusBadge status={displayStatus as HumanVerdict} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Referans Örnekler (Gold Standard) (inside right column in logic mode) */}
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                  Referans Örnekler (Gold Standard)
                </h2>
              </div>
              <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                {GOLD_STANDARDS.map((ex) => (
                  <div
                    key={ex.frame_type}
                    className="border border-hair border-carbon-550/50 p-2.5 bg-carbon-950"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[9px] text-carbon-300 bg-carbon-800 px-1.5 py-0.5">
                        {ex.frame_type}
                      </span>
                    </div>
                    <p className="text-2xs text-carbon-200 italic">"{ex.sentence_text}"</p>
                    <p className="text-[10px] text-carbon-400 mt-1 font-sans">{ex.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Column 3: Verdict Form + Reference Examples (only for AI mode) */}
        {mode === 'ai' && (
          <div className="col-span-1 space-y-6">
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
              <div className="flex items-center gap-2 mb-6">
                <AlertCircle className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">Karar Formu</h2>
              </div>
              <VerdictForm
                logId={Number(logId)}
                onSubmitted={() => toast.success('İnceleme tamamlandı.')}
              />
            </div>

            {/* Referans Örnekler (Gold Standard) */}
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                  Referans Örnekler (Gold Standard)
                </h2>
              </div>
              <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                {GOLD_STANDARDS.map((ex) => (
                  <div
                    key={ex.frame_type}
                    className="border border-hair border-carbon-550/50 p-2.5 bg-carbon-950"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[9px] text-carbon-300 bg-carbon-800 px-1.5 py-0.5">
                        {ex.frame_type}
                      </span>
                    </div>
                    <p className="text-2xs text-carbon-200 italic">"{ex.sentence_text}"</p>
                    <p className="text-[10px] text-carbon-400 mt-1 font-sans">{ex.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <FileText className="w-4 h-4 text-carbon-400" strokeWidth={1.5} />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">Benzer Vakalar</h2>
        </div>
        <DataTable
          columns={[
            {
              key: 'text',
              header: 'Cümle',
              render: (r) => (
                <span className="text-sm text-carbon-200">{truncate(r.sentence_text, 100)}</span>
              ),
            },
            {
              key: 'country',
              header: 'Ülke',
              width: '100px',
              render: (r) => <span className="text-2xs text-carbon-300">{r.country}</span>,
            },
            {
              key: 'speaker',
              header: 'Konuşmacı',
              width: '120px',
              render: (r) => <span className="text-2xs text-carbon-300">{r.speaker_name}</span>,
            },
            {
              key: 'value',
              header: 'Değer',
              width: '80px',
              render: (r) => {
                const val =
                  typeof r.actual_value === 'number'
                    ? r.actual_value.toFixed(3)
                    : r.actual_value !== null && r.actual_value !== undefined
                      ? String(r.actual_value)
                      : '-';
                return <span className="font-mono text-2xs text-carbon-200">{val}</span>;
              },
            },
            {
              key: 'verdict',
              header: 'Karar',
              width: '120px',
              render: (r) => <StatusBadge status={r.previous_verdict} />,
            },
            {
              key: 'note',
              header: 'Not',
              render: (r) => (
                <span className="text-2xs text-carbon-400 max-w-xs truncate">
                  {r.previous_note}
                </span>
              ),
            },
          ]}
          data={similar}
          keyExtractor={(r) => r.sentence_text}
        />
      </div>
    </div>
  );
};
