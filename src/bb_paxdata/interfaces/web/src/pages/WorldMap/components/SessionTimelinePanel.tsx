// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/SessionTimelinePanel.tsx

import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
  BarChart2,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  Globe,
  Map,
  RefreshCw,
  RotateCcw,
  Square,
  TrendingUp,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getSessionTimeline } from '../../../api/visualizationApi';
import type { RelationshipType, SessionTimeline } from '../../../types/visualization';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';
import { useVizStore } from '../../../store/vizStore';

// ─── Constants ────────────────────────────────────────────────────────────────

const SESSION_LABELS: Record<string, string> = {
  '01_ahmed_al-sharaa': 'Ahmed Al-Sharaa Röportajı',
  '02_cevdet_yılmaz': 'Cevdet Yılmaz Açılış Konuşması',
  '03_erdoğan': 'Erdoğan Konuşması',
  '04_avrupa_başkanları': 'Avrupa Liderleri Paneli',
  '05_gazze_konuşması': 'Gazze Konuşması',
  '06_mevlüt_çavuşoğlu_ve_cumhurbaşkanları': 'Çavuşoğlu & Cumhurbaşkanları',
  '07_sergei_lavrov': 'Lavrov Konuşması',
  '08_somali': 'Somali Zirvesi',
  '09_tom_barrack': 'Tom Barrack Açıklaması',
  '10_ukrayna_dışişleri_bakanı': 'Ukrayna Dışişleri Bakanı',
  '11_hakan_fidan': 'Hakan Fidan Açıklaması',
  '12_climate': 'İklim Görüşmeleri',
};

const SESSION_SHORT_LABELS: Record<string, string> = {
  '01_ahmed_al-sharaa': 'Al-Sharaa',
  '02_cevdet_yılmaz': 'C. Yılmaz',
  '03_erdoğan': 'Erdoğan',
  '04_avrupa_başkanları': 'Avrupa',
  '05_gazze_konuşması': 'Gazze',
  '06_mevlüt_çavuşoğlu_ve_cumhurbaşkanları': 'Çavuşoğlu',
  '07_sergei_lavrov': 'Lavrov',
  '08_somali': 'Somali',
  '09_tom_barrack': 'Barrack',
  '10_ukrayna_dışişleri_bakanı': 'Ukrayna',
  '11_hakan_fidan': 'H. Fidan',
  '12_climate': 'İklim',
};

/** Palette for up to 12 chart lines */
const LINE_COLORS = [
  '#818cf8',
  '#34d399',
  '#fb923c',
  '#f472b6',
  '#60a5fa',
  '#facc15',
  '#a78bfa',
  '#4ade80',
  '#f87171',
  '#22d3ee',
  '#e879f9',
  '#a3e635',
];

// ─── Types ────────────────────────────────────────────────────────────────────

type SortKey = 'label' | 'sentiment' | 'emotion' | 'countries' | 'praise' | 'accusation';
type SortDir = 'asc' | 'desc';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getLabel(session: SessionTimeline): string {
  return SESSION_LABELS[session.sessionId] || session.sessionLabel || session.sessionId;
}

function getShortLabel(sessionId: string): string {
  return SESSION_SHORT_LABELS[sessionId] || sessionId;
}

function formatSentiment(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2);
}

function emotionBadgeClass(emotion: string): string {
  switch (emotion) {
    case 'cooperative':
      return 'bg-emerald-900/40 text-emerald-300 border-emerald-700/40';
    case 'constructive':
      return 'bg-blue-900/40 text-blue-300 border-blue-700/40';
    case 'concerned':
      return 'bg-amber-900/40 text-amber-300 border-amber-700/40';
    case 'neutral_cautious':
      return 'bg-carbon-700 text-carbon-300 border-carbon-600';
    default:
      return 'bg-carbon-800 text-carbon-400 border-carbon-600';
  }
}

// ─── SessionChip ──────────────────────────────────────────────────────────────

interface SessionChipProps {
  session: SessionTimeline;
  selected: boolean;
  colorIndex: number;
  onToggle: (id: string) => void;
}

const SessionChip: React.FC<SessionChipProps> = ({ session, selected, colorIndex, onToggle }) => {
  const color = LINE_COLORS[colorIndex % LINE_COLORS.length];
  return (
    <button
      type="button"
      onClick={() => onToggle(session.sessionId)}
      title={getLabel(session)}
      className={`group relative flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium border transition-all duration-150 rounded-none truncate max-w-[180px] ${
        selected
          ? 'bg-carbon-700 border-carbon-500 text-carbon-100'
          : 'bg-carbon-900 border-carbon-600 text-carbon-400 hover:border-carbon-500 hover:text-carbon-300'
      }`}
    >
      {selected ? (
        <CheckSquare className="w-3 h-3 flex-shrink-0" style={{ color }} />
      ) : (
        <Square className="w-3 h-3 flex-shrink-0 text-carbon-600" />
      )}
      <span className="truncate">{getShortLabel(session.sessionId)}</span>
    </button>
  );
};

// ─── SessionCard ──────────────────────────────────────────────────────────────

interface SessionCardProps {
  session: SessionTimeline;
  colorIndex: number;
  onShowOnMap: (sessionId: string) => void;
}

const SessionCard: React.FC<SessionCardProps> = ({ session, colorIndex, onShowOnMap }) => {
  const [expanded, setExpanded] = useState(false);
  const label = getLabel(session);
  const color = LINE_COLORS[colorIndex % LINE_COLORS.length];
  const neutralCount = Math.max(
    0,
    (session.countries?.length ?? 0) * 10 - session.praiseCount - session.accusationCount,
  );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.18 }}
      className="border border-carbon-600 bg-carbon-900/60 rounded-none overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-carbon-800/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: color }}
          />
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-carbon-100 truncate">{label}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className="text-[11px] font-mono font-bold"
                style={{ color: sentimentToColor(session.avgSentiment) }}
              >
                {formatSentiment(session.avgSentiment)}
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.5 border rounded-none ${emotionBadgeClass(session.dominantEmotion)}`}
              >
                {session.dominantEmotion || '—'}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0 ml-3">
          <div className="text-[10px] text-carbon-400 hidden sm:block">
            <span className="text-carbon-200">{session.countries?.length ?? 0}</span> ülke
          </div>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-carbon-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-carbon-400" />
          )}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4 border-t border-carbon-700/50">
              {/* Active Countries */}
              <div className="pt-3">
                <div className="text-[10px] uppercase tracking-wider text-carbon-400 font-semibold mb-2">
                  Aktif Ülkeler
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(session.countries ?? []).slice(0, 12).map((c) => (
                    <span
                      key={c}
                      className="px-2 py-0.5 text-[10px] bg-carbon-800 border border-carbon-600 text-carbon-300 rounded-none"
                    >
                      {c}
                    </span>
                  ))}
                  {(session.countries?.length ?? 0) > 12 && (
                    <span className="px-2 py-0.5 text-[10px] text-carbon-500">
                      +{(session.countries?.length ?? 0) - 12} daha
                    </span>
                  )}
                </div>
              </div>

              {/* Top Relationships */}
              {session.topRelationships && session.topRelationships.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-carbon-400 font-semibold mb-2">
                    Top İlişkiler
                  </div>
                  <div className="space-y-1">
                    {session.topRelationships.slice(0, 5).map((rel, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-[11px] bg-carbon-800/50 px-3 py-1.5 border border-carbon-700/50"
                      >
                        <span className="text-carbon-300">
                          {rel.from}
                          <span className="text-carbon-500 mx-1.5">→</span>
                          {rel.to}
                        </span>
                        <div className="flex items-center gap-2">
                          <span
                            className="px-1.5 py-0.5 text-[9px] font-semibold rounded-none border"
                            style={{
                              color: RELATIONSHIP_COLORS[rel.type as RelationshipType] ?? '#6b7280',
                              borderColor:
                                (RELATIONSHIP_COLORS[rel.type as RelationshipType] ?? '#6b7280') +
                                '55',
                              backgroundColor:
                                (RELATIONSHIP_COLORS[rel.type as RelationshipType] ?? '#6b7280') +
                                '15',
                            }}
                          >
                            {rel.type}
                          </span>
                          <span
                            className="font-mono font-bold text-[11px]"
                            style={{ color: sentimentToColor(rel.score) }}
                          >
                            {formatSentiment(rel.score)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Counts */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-emerald-950/30 border border-emerald-800/30 px-3 py-2 text-center rounded-none">
                  <div className="text-[10px] text-emerald-400 font-medium">Övgü</div>
                  <div className="text-base font-bold text-emerald-300 font-mono">
                    {session.praiseCount}
                  </div>
                </div>
                <div className="bg-red-950/30 border border-red-800/30 px-3 py-2 text-center rounded-none">
                  <div className="text-[10px] text-red-400 font-medium">İtham</div>
                  <div className="text-base font-bold text-red-300 font-mono">
                    {session.accusationCount}
                  </div>
                </div>
                <div className="bg-carbon-800/50 border border-carbon-700/50 px-3 py-2 text-center rounded-none">
                  <div className="text-[10px] text-carbon-400 font-medium">Nötr</div>
                  <div className="text-base font-bold text-carbon-200 font-mono">
                    {neutralCount}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => onShowOnMap(session.sessionId)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium bg-indigo-900/40 border border-indigo-700/50 text-indigo-300 hover:bg-indigo-800/50 hover:text-indigo-100 transition-colors rounded-none"
                >
                  <Map className="w-3 h-3" />
                  Bu oturumu haritada göster
                </button>
                <button
                  type="button"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium bg-carbon-800 border border-carbon-600 text-carbon-300 hover:bg-carbon-700 hover:text-carbon-100 transition-colors rounded-none"
                >
                  <BarChart2 className="w-3 h-3" />
                  Detaylı analiz →
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

// ─── Custom Tooltip ────────────────────────────────────────────────────────────

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

const CustomLineTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-carbon-900 border border-carbon-600 rounded-none p-3 shadow-xl min-w-[180px]">
      <div className="text-[11px] font-semibold text-carbon-200 mb-2 border-b border-carbon-700 pb-1">
        {label}
      </div>
      <div className="space-y-1">
        {payload.map((p) => (
          <div key={p.name} className="flex items-center justify-between gap-4 text-[11px]">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
              <span className="text-carbon-300 truncate max-w-[120px]">{p.name}</span>
            </div>
            <span className="font-mono font-bold" style={{ color: sentimentToColor(p.value) }}>
              {formatSentiment(p.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Main Component ────────────────────────────────────────────────────────────

export const SessionTimelinePanel: React.FC = () => {
  const { setFilter, setActiveTab } = useVizStore();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>('label');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const {
    data: sessions = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['session-timeline'],
    queryFn: () => getSessionTimeline(),
    staleTime: 5 * 60 * 1000,
  });

  // ── Selection Helpers ──────────────────────────────────────────────────────

  const toggleSession = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(sessions.map((s) => s.sessionId)));
  }, [sessions]);

  const resetSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // Sessions shown (all if nothing selected)
  const selectedSessions = useMemo(() => {
    if (selectedIds.size === 0) return sessions;
    return sessions.filter((s) => selectedIds.has(s.sessionId));
  }, [sessions, selectedIds]);

  // ── Sorting ────────────────────────────────────────────────────────────────

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortedSessions = useMemo(() => {
    const list = [...selectedSessions];
    list.sort((a, b) => {
      let av: string | number = 0;
      let bv: string | number = 0;
      switch (sortKey) {
        case 'label':
          av = getLabel(a);
          bv = getLabel(b);
          break;
        case 'sentiment':
          av = a.avgSentiment;
          bv = b.avgSentiment;
          break;
        case 'emotion':
          av = a.dominantEmotion || '';
          bv = b.dominantEmotion || '';
          break;
        case 'countries':
          av = a.countries?.length ?? 0;
          bv = b.countries?.length ?? 0;
          break;
        case 'praise':
          av = a.praiseCount;
          bv = b.praiseCount;
          break;
        case 'accusation':
          av = a.accusationCount;
          bv = b.accusationCount;
          break;
      }
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return list;
  }, [selectedSessions, sortKey, sortDir]);

  // ── Chart Data ─────────────────────────────────────────────────────────────

  const trendChartData = useMemo(() => {
    return sessions.map((s) => ({
      label: getShortLabel(s.sessionId),
      sessionId: s.sessionId,
      'Tüm Oturumlar': s.avgSentiment,
    }));
  }, [sessions]);

  // ── Map Navigation ─────────────────────────────────────────────────────────

  const handleShowOnMap = useCallback(
    (sessionId: string) => {
      setFilter('selectedSessions', [sessionId]);
      setActiveTab('choropleth');
    },
    [setFilter, setActiveTab],
  );

  // ── Utilities ──────────────────────────────────────────────────────────────

  const getColorIndexForSession = (sessionId: string): number =>
    sessions.findIndex((s) => s.sessionId === sessionId);

  const SortIcon: React.FC<{ colKey: SortKey }> = ({ colKey }) => {
    if (sortKey !== colKey) return <span className="text-carbon-600 ml-1 text-[9px]">⇅</span>;
    return sortDir === 'asc' ? (
      <ChevronUp className="w-3 h-3 ml-1 text-indigo-400 inline" />
    ) : (
      <ChevronDown className="w-3 h-3 ml-1 text-indigo-400 inline" />
    );
  };

  // ── Loading / Error ─────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-7 h-7 text-indigo-400 animate-spin" />
          <span className="text-sm text-carbon-400">Oturumlar yükleniyor…</span>
        </div>
      </div>
    );
  }

  if (isError || sessions.length === 0) {
    return (
      <div className="border border-carbon-550 bg-carbon-900 p-6 text-sm text-carbon-300">
        <p className="font-semibold text-carbon-50">Oturum verisi alınamadı.</p>
        <p className="mt-2 text-carbon-400">API bağlantısını kontrol edin.</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-4 flex items-center gap-2 px-4 py-2 bg-carbon-800 border border-carbon-550 text-carbon-300 hover:text-carbon-100 hover:bg-carbon-700 transition-colors text-xs rounded-none"
        >
          <RefreshCw className="w-4 h-4" />
          Tekrar Dene
        </button>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const TABLE_COLS: Array<{ key: SortKey; label: string }> = [
    { key: 'label', label: 'Oturum' },
    { key: 'sentiment', label: 'Sentiment' },
    { key: 'emotion', label: 'Dom. Duygu' },
    { key: 'countries', label: 'Aktif Ülkeler' },
    { key: 'praise', label: 'Övgü' },
    { key: 'accusation', label: 'İtham' },
  ];

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      {/* ── Session Selector ───────────────────────────────────────────────── */}
      <div className="bg-carbon-900 border border-carbon-550 rounded-none p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-carbon-100">Oturum Seçici</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-carbon-400">
              {selectedIds.size === 0 ? 'Tümü gösteriliyor' : `${selectedIds.size} oturum seçili`}
            </span>
            <button
              type="button"
              onClick={selectAll}
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] bg-indigo-900/40 border border-indigo-700/50 text-indigo-300 hover:bg-indigo-800/50 transition-colors rounded-none"
            >
              <CheckSquare className="w-3 h-3" />
              Tümünü Seç
            </button>
            <button
              type="button"
              onClick={resetSelection}
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] bg-carbon-800 border border-carbon-600 text-carbon-400 hover:text-carbon-200 hover:bg-carbon-700 transition-colors rounded-none"
            >
              <RotateCcw className="w-3 h-3" />
              Sıfırla
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {sessions.map((s, i) => (
            <SessionChip
              key={s.sessionId}
              session={s}
              selected={selectedIds.has(s.sessionId)}
              colorIndex={i}
              onToggle={toggleSession}
            />
          ))}
        </div>
      </div>

      {/* ── Sentiment Trend Chart ──────────────────────────────────────────── */}
      <div className="bg-carbon-900 border border-carbon-550 rounded-none p-4">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-carbon-100">Sentiment Trend</h3>
          <span className="text-[11px] text-carbon-400">— tüm 12 oturum</span>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={trendChartData} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: '#71717a', fontSize: 10 }}
              angle={-35}
              textAnchor="end"
              interval={0}
              height={56}
              tickLine={false}
              axisLine={{ stroke: '#3f3f46' }}
            />
            <YAxis
              domain={[-1, 1]}
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickFormatter={(v: number) => v.toFixed(1)}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 2" />
            <Tooltip content={<CustomLineTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '10px', color: '#a1a1aa', paddingTop: '8px' }}
              formatter={() => 'Avg Sentiment'}
            />
            <Line
              type="monotone"
              dataKey="Tüm Oturumlar"
              stroke="#818cf8"
              strokeWidth={2}
              dot={(props) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const { cx, cy, payload } = props as any;
                const isHighlighted =
                  selectedIds.size === 0 || selectedIds.has(payload.sessionId as string);
                const idx = getColorIndexForSession(payload.sessionId as string);
                const dotColor = isHighlighted
                  ? (LINE_COLORS[idx % LINE_COLORS.length] ?? '#818cf8')
                  : '#3f3f46';
                return (
                  <circle
                    key={payload.sessionId as string}
                    cx={cx as number}
                    cy={cy as number}
                    r={isHighlighted ? 5 : 3}
                    fill={dotColor}
                    stroke={isHighlighted ? '#1c1c21' : 'none'}
                    strokeWidth={2}
                    opacity={isHighlighted ? 1 : 0.35}
                  />
                );
              }}
              activeDot={{ r: 6, stroke: '#818cf8', strokeWidth: 2, fill: '#1c1c21' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* ── Comparison Table ───────────────────────────────────────────────── */}
      <div className="bg-carbon-900 border border-carbon-550 rounded-none overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-carbon-600">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-carbon-100">Karşılaştırma Tablosu</h3>
          </div>
          <span className="text-[11px] text-carbon-400">{sortedSessions.length} oturum</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-carbon-700 bg-carbon-800/50">
                {TABLE_COLS.map((col) => (
                  <th
                    key={col.key}
                    className="px-3 py-2 text-left text-[10px] uppercase tracking-wider text-carbon-400 font-semibold cursor-pointer hover:text-carbon-200 select-none whitespace-nowrap"
                    onClick={() => handleSort(col.key)}
                  >
                    {col.label}
                    <SortIcon colKey={col.key} />
                  </th>
                ))}
                <th className="px-3 py-2 text-left text-[10px] uppercase tracking-wider text-carbon-400 font-semibold whitespace-nowrap">
                  Eylem
                </th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {sortedSessions.map((s, i) => {
                  const colorIdx = getColorIndexForSession(s.sessionId);
                  const dotColor = LINE_COLORS[colorIdx % LINE_COLORS.length] ?? '#818cf8';
                  return (
                    <motion.tr
                      key={s.sessionId}
                      layout
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 8 }}
                      transition={{ duration: 0.15, delay: i * 0.02 }}
                      className="border-b border-carbon-700/50 hover:bg-carbon-800/30 transition-colors"
                    >
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2 max-w-[200px]">
                          <div
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ backgroundColor: dotColor }}
                          />
                          <span className="text-carbon-200 font-medium truncate">
                            {getLabel(s)}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className="font-mono font-bold"
                          style={{ color: sentimentToColor(s.avgSentiment) }}
                        >
                          {formatSentiment(s.avgSentiment)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`px-1.5 py-0.5 text-[10px] border rounded-none ${emotionBadgeClass(s.dominantEmotion)}`}
                        >
                          {s.dominantEmotion || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1">
                          <Globe className="w-3 h-3 text-carbon-500" />
                          <span className="text-carbon-200 font-mono">
                            {s.countries?.length ?? 0}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="text-emerald-400 font-mono font-semibold">
                          {s.praiseCount}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="text-red-400 font-mono font-semibold">
                          {s.accusationCount}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <button
                          type="button"
                          onClick={() => handleShowOnMap(s.sessionId)}
                          className="flex items-center gap-1 px-2 py-1 text-[10px] bg-indigo-900/30 border border-indigo-800/40 text-indigo-400 hover:bg-indigo-800/40 hover:text-indigo-200 transition-colors rounded-none whitespace-nowrap"
                        >
                          <Map className="w-3 h-3" />
                          Haritada Göster
                        </button>
                      </td>
                    </motion.tr>
                  );
                })}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Session Detail Cards ───────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <BarChart2 className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-carbon-100">Oturum Detay Kartları</h3>
          <span className="text-[11px] text-carbon-400">— genişletmek için tıklayın</span>
        </div>
        <div className="space-y-2">
          <AnimatePresence>
            {sortedSessions.map((s) => (
              <SessionCard
                key={s.sessionId}
                session={s}
                colorIndex={getColorIndexForSession(s.sessionId)}
                onShowOnMap={handleShowOnMap}
              />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
