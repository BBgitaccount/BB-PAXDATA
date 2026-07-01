import { useQuery } from '@tanstack/react-query';
import { Activity, Clock, Info, RefreshCw, TrendingUp, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { apiClient } from '@/services/apiClient';
import type { TemporalDriftData } from '@/types';
import { cn } from '@/utils/helpers';

export const TemporalDrift = () => {
  const toast = useToast();
  const { t } = useTranslation();
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('');

  // Fetch temporal drift data
  const driftQuery = useQuery({
    queryKey: ['temporal-drift', selectedSpeaker],
    queryFn: () => {
      const params = new URLSearchParams();
      if (selectedSpeaker) params.set('speaker_id', selectedSpeaker);
      return apiClient.get<TemporalDriftData>(`/api/v1/dashboard/drift?${params.toString()}`);
    },
    staleTime: 1000 * 30, // 30 sn - drift analysis data for interactive exploration
  });

  // Sync selected speaker state on load
  useEffect(() => {
    if (driftQuery.data && driftQuery.data.selected_speaker && !selectedSpeaker) {
      setSelectedSpeaker(driftQuery.data.selected_speaker);
    }
  }, [driftQuery.data, selectedSpeaker]);

  const handleRefresh = () => {
    void driftQuery.refetch();
    toast.info('Veriler tazeleniyor...');
  };

  // Handle errors
  useEffect(() => {
    if (driftQuery.isError) {
      toast.error('Temporal drift verileri yüklenemedi.');
    }
  }, [driftQuery.isError, toast]);

  if (driftQuery.isPending) {
    return (
      <div className="space-y-8">
        <div className="h-10 shimmer w-1/4" />
        <div className="grid grid-cols-3 gap-4">
          <div className="h-28 shimmer" />
          <div className="h-28 shimmer" />
          <div className="h-28 shimmer" />
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="h-80 shimmer" />
          <div className="h-80 shimmer" />
        </div>
      </div>
    );
  }

  if (driftQuery.isError || !driftQuery.data) {
    return (
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-8 text-center space-y-4">
        <p className="text-sm text-carbon-200 font-semibold">Drift analizi verileri yüklenemedi.</p>
        <button type="button" onClick={handleRefresh} className="btn-primary text-xs px-4 py-2">
          Yeniden Dene
        </button>
      </div>
    );
  }

  const { garch, half_life, dki, drift_events, speakers } = driftQuery.data;

  // Prepare GARCH chart data (sentiment vs volatility series)
  const garchChartData = garch.sentiment_series.map((val, idx) => ({
    sentence: `Cümle ${idx + 1}`,
    sentiment: val,
    volatility: garch.volatilities_series[idx] || 0.0,
  }));

  // Prepare Salience count chart data
  const salienceChartData = half_life.counts_series.map((count, idx) => ({
    panel: `Panel ${idx + 1}`,
    count: count,
  }));

  // Prepare DKI trend chart data
  const dkiChartData = dki.map((item) => ({
    session: item.session_id,
    dki: item.dki_score,
    velocity: item.velocity,
    shift: item.semantic_shift,
    loading: item.debate_loading,
  }));

  // Helper styles for severity and regimes
  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'HIGH_VOLATILITY':
        return 'text-red-400 bg-red-950/40 border-red-900';
      case 'ARCH_EFFECTS':
        return 'text-orange-400 bg-orange-950/40 border-orange-900';
      default:
        return 'text-green-400 bg-green-950/40 border-green-900';
    }
  };

  const getPermanenceColor = (permanence: string) => {
    switch (permanence) {
      case 'FLASH':
        return 'text-red-400 bg-red-950/40 border-red-900';
      case 'TACTICAL':
        return 'text-orange-400 bg-orange-950/40 border-orange-900';
      case 'STRATEGIC':
        return 'text-blue-400 bg-blue-950/40 border-blue-900';
      default:
        return 'text-green-400 bg-green-950/40 border-green-900';
    }
  };

  const getDriftTypeColor = (type: string) => {
    switch (type) {
      case 'SENTIMENT':
        return 'text-red-400 border-red-900/60 bg-red-950/20';
      case 'TOPIC':
        return 'text-blue-400 border-blue-900/60 bg-blue-950/20';
      case 'RISK':
        return 'text-orange-400 border-orange-900/60 bg-orange-950/20';
      default:
        return 'text-carbon-300 border-carbon-700 bg-carbon-800/40';
    }
  };

  const getSeverityStyle = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
        return 'bg-red-500 text-carbon-950';
      case 'HIGH':
        return 'bg-orange-500 text-carbon-950';
      case 'MEDIUM':
        return 'bg-amber-500 text-carbon-950';
      default:
        return 'bg-carbon-700 text-carbon-300';
    }
  };

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('drift.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('drift.desc')}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-xs border-carbon-600 hover:bg-carbon-800"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Tazele
        </button>
      </div>

      {/* Speaker Selector Controls */}
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col md:flex-row items-center gap-4">
        <div className="flex flex-col gap-1.5 w-full md:w-80">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <User className="w-3.5 h-3.5" />
            Aktör Seçimi
          </label>
          <select
            value={selectedSpeaker}
            onChange={(e) => setSelectedSpeaker(e.target.value)}
            className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs px-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400"
          >
            {speakers.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="hidden md:flex items-center gap-2 text-3xs text-carbon-450 mt-4">
          <Info className="w-3.5 h-3.5" />
          <span>Farklı bir aktörün zaman serisi sapmalarını görmek için listeden seçim yapın.</span>
        </div>
      </div>

      {/* KPI Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* KPI 1: GARCH */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5" />
              GARCH (1,1) Volatilite Puanı
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2">
              {garch.sentiment_volatility.toFixed(4)}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={cn(
                'text-4xs px-2 py-0.5 border font-mono font-semibold tracking-wider uppercase',
                getRegimeColor(garch.volatility_regime),
              )}
            >
              {garch.volatility_regime.replace('_', ' ')}
            </span>
          </div>
        </div>

        {/* KPI 2: Half Life */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Salience Yarı-Ömrü (Half-life)
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2">
              {half_life.salience_half_life === 999.0
                ? '∞ (Stabil)'
                : `${half_life.salience_half_life.toFixed(2)} Panel`}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={cn(
                'text-4xs px-2 py-0.5 border font-mono font-semibold tracking-wider uppercase',
                getPermanenceColor(half_life.agenda_permanence),
              )}
            >
              {half_life.agenda_permanence} Gündem
            </span>
            <span className="text-4xs font-mono text-carbon-450">
              Azalma: {half_life.decay_rate.toFixed(4)}
            </span>
          </div>
        </div>

        {/* KPI 3: Latest DKI */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-28">
          <div>
            <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" />
              Güncel DKI Puanı
            </span>
            <div className="text-lg font-mono font-bold text-carbon-100 mt-2">
              {dki.length > 0 ? dki[dki.length - 1].dki_score.toFixed(4) : 'Veri Yok'}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            {dki.length > 0 ? (
              <span className="text-4xs font-mono text-carbon-350 uppercase">
                Oturum: {dki[dki.length - 1].session_id}
              </span>
            ) : (
              <span className="text-4xs text-carbon-500">DKI kaydı bulunmamaktadır</span>
            )}
          </div>
        </div>
      </div>

      {/* Volatility & Salience Chart Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* GARCH Chart */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Sentiment ve GARCH Volatilitesi
            </h3>
            <p className="text-micro text-carbon-400 mt-1">
              Cümleler boyunca sentiment dalgalanması (VADER) ve GARCH conditional variance takibi
            </p>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={garchChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
                <XAxis
                  dataKey="sentence"
                  tick={{
                    fill: 'var(--text-tertiary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: 'var(--border-hair)' }}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="left"
                  tick={{
                    fill: 'var(--text-secondary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                  domain={[-1, 1]}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{
                    fill: 'var(--text-secondary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 1]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-tertiary)',
                    border: '0.5px solid var(--border-hair)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono',
                    color: 'var(--text-primary)',
                    borderRadius: 0,
                  }}
                />
                <Legend
                  wrapperStyle={{
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                    color: 'var(--text-secondary)',
                  }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="sentiment"
                  stroke="var(--text-secondary)"
                  strokeWidth={1}
                  dot={false}
                  name="Sentiment"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="volatility"
                  stroke="var(--text-primary)"
                  strokeWidth={1.8}
                  dot={false}
                  name="GARCH Volatility"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Salience count bar chart */}
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Entity Salience Dağılımı (Panel Bazında)
            </h3>
            <p className="text-micro text-carbon-400 mt-1">
              Aktörün konuşma yoğunluğunun (cümle adedi) zamansal değişimi
            </p>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={salienceChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
                <XAxis
                  dataKey="panel"
                  tick={{
                    fill: 'var(--text-tertiary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: 'var(--border-hair)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{
                    fill: 'var(--text-secondary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-tertiary)',
                    border: '0.5px solid var(--border-hair)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono',
                    color: 'var(--text-primary)',
                    borderRadius: 0,
                  }}
                />
                <Bar
                  dataKey="count"
                  fill="var(--text-tertiary)"
                  stroke="var(--border-hair)"
                  strokeWidth={1}
                  barSize={24}
                  name="Cümle Sayısı"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* DKI Component Trajectories */}
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
            DKI Bileşenleri ve Zamansal Trajeksiyon
          </h3>
          <p className="text-micro text-carbon-400 mt-1">
            Dynamic Keyness Index bileşenlerinin (Velocity, Semantic Shift ve Debate Loading)
            oturumlar bazındaki seyri
          </p>
        </div>
        {dki.length === 0 ? (
          <div className="h-60 border border-dashed border-carbon-800 bg-carbon-950/20 flex flex-col items-center justify-center text-xs text-carbon-500">
            Aktör için dki_results kaydı bulunamadı.
          </div>
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dkiChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
                <XAxis
                  dataKey="session"
                  tick={{
                    fill: 'var(--text-tertiary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={{ stroke: 'var(--border-hair)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{
                    fill: 'var(--text-secondary)',
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono',
                  }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 1.2]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-tertiary)',
                    border: '0.5px solid var(--border-hair)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono',
                    color: 'var(--text-primary)',
                    borderRadius: 0,
                  }}
                />
                <Legend
                  wrapperStyle={{
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                    color: 'var(--text-secondary)',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="dki"
                  stroke="var(--text-primary)"
                  strokeWidth={2}
                  name="DKI Composite Score"
                />
                <Line
                  type="monotone"
                  dataKey="velocity"
                  stroke="var(--signal-pass)"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  name="Debate Velocity"
                />
                <Line
                  type="monotone"
                  dataKey="shift"
                  stroke="var(--signal-fail)"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  name="Semantic Shift"
                />
                <Line
                  type="monotone"
                  dataKey="loading"
                  stroke="var(--signal-warn)"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  name="Debate Loading"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Logged Drift Events */}
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Kayıtlı Temporal Drift Olayları
            </h3>
            <p className="text-micro text-carbon-400 mt-1">
              Veritabanında kayıtlı olan, CUSUM ve Markov geçişleri algoritmalarınca tetiklenen
              olaylar
            </p>
          </div>
          <span className="text-3xs font-mono bg-carbon-850 px-2 py-1 text-carbon-355 border border-hair border-carbon-750">
            {drift_events.length} Olay
          </span>
        </div>

        {drift_events.length === 0 ? (
          <div className="py-8 text-center text-xs text-carbon-500 border border-dashed border-carbon-800 bg-carbon-950/20">
            Bu aktör için tetiklenmiş herhangi bir drift/sapma olayı bulunmamaktadır.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-hair border-carbon-800 text-carbon-450 uppercase tracking-widest text-3xs font-semibold">
                  <th className="py-2.5 px-3">Tip</th>
                  <th className="py-2.5 px-3">Panel ID</th>
                  <th className="py-2.5 px-3">Şiddet</th>
                  <th className="py-2.5 px-3">Ön/Son Durum (Drift States)</th>
                  <th className="py-2.5 px-3">Algoritma</th>
                  <th className="py-2.5 px-3 text-right">Güven Puanı</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hair divide-carbon-800">
                {drift_events.map((evt) => (
                  <tr key={evt.id} className="hover:bg-carbon-850/30 transition-colors">
                    <td className="py-3 px-3">
                      <span
                        className={cn(
                          'text-4xs px-2 py-0.5 border font-semibold tracking-wider font-mono',
                          getDriftTypeColor(evt.drift_type),
                        )}
                      >
                        {evt.drift_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-2xs text-carbon-300">{evt.panel_id}</td>
                    <td className="py-3 px-3">
                      <span
                        className={cn(
                          'text-4xs px-1.5 py-0.5 font-semibold font-mono',
                          getSeverityStyle(evt.severity),
                        )}
                      >
                        {evt.severity}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-2xs text-carbon-350">
                      {evt.before_state && evt.after_state ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-carbon-400">"{evt.before_state}"</span>
                          <span className="text-carbon-600">→</span>
                          <span className="text-carbon-200 font-medium">"{evt.after_state}"</span>
                        </div>
                      ) : (
                        <span className="text-carbon-500">-</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-2xs font-mono text-carbon-450">
                      {evt.algorithm}
                    </td>
                    <td className="py-3 px-3 font-mono text-2xs text-carbon-300 text-right">
                      {evt.confidence.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
