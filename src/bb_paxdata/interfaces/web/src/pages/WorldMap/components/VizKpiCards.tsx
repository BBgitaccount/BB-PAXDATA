// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/VizKpiCards.tsx

import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Activity, AlertTriangle, Smile, TrendingUp, Users, Zap } from 'lucide-react';
import React, { useMemo } from 'react';
import { Area, AreaChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useVizStore } from '../../../store/vizStore';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';

// Count-up animation hook
function useCountUp(value: number) {
  const spring = useSpring(useMotionValue(0), {
    mass: 0.8,
    stiffness: 75,
    damping: 20,
  });

  const display = useTransform(spring, (current) => Math.round(current));

  // Trigger animation when value changes
  React.useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  return display;
}

// Animated number component
const AnimatedNumber = ({ value }: { value: number }) => {
  const display = useCountUp(value);
  return <motion.span>{display}</motion.span>;
};

const KpiCard = ({ children }: { children: React.ReactNode }) => (
  <motion.div
    className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] p-4 hover:translate-y-[-2px] hover:shadow-lg transition-all duration-200"
    whileHover={{ y: -2 }}
  >
    {children}
  </motion.div>
);

// Card 1: Total Interactions
const TotalInteractionsCard = ({
  data,
}: {
  data: { totalInteractions?: number; activePairs?: number; trend?: number };
}) => {
  const totalInteractions = data?.totalInteractions || 1488;
  const activePairs = data?.activePairs || 206;
  const trend = data?.trend || 12;

  // Mock sparkline data
  const sparklineData = useMemo(() => {
    return Array.from({ length: 12 }, () => ({
      value: Math.floor(Math.random() * 500) + 1000,
    }));
  }, []);

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">Etkileşim Hacmi</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-semibold text-gray-100 font-mono">
          <AnimatedNumber value={totalInteractions} />
        </span>
        <span className={`text-xs font-medium ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          ▲ {trend}%
        </span>
      </div>
      <div className="text-xs text-gray-400 mb-3">Aktif Çiftler: {activePairs}</div>
      <ResponsiveContainer width="100%" height={32}>
        <AreaChart data={sparklineData}>
          <defs>
            <linearGradient id="sparkGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke="#818cf8"
            strokeWidth={1.5}
            fill="url(#sparkGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </KpiCard>
  );
};

// Card 2: Average Sentiment
const AverageSentimentCard = ({ data }: { data: { avgSentiment?: number } }) => {
  const avgSentiment = data?.avgSentiment || 0.14;
  const sentimentColor = sentimentToColor(avgSentiment);
  const sentimentLabel = avgSentiment > 0.3 ? 'Pozitif' : avgSentiment < -0.3 ? 'Negatif' : 'Nötr';
  const emoji = avgSentiment > 0.3 ? '😊' : avgSentiment < -0.3 ? '😟' : '😐';

  // Normalize to 0-100 for progress bar
  const progress = ((avgSentiment + 1) / 2) * 100;

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <Smile className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">Global Sentiment</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-semibold font-mono" style={{ color: sentimentColor }}>
          {avgSentiment >= 0 ? '+' : ''}
          {avgSentiment.toFixed(2)}
        </span>
        <span className="text-xs text-gray-400">
          {emoji} {sentimentLabel}
        </span>
      </div>
      <div className="relative h-2 bg-gray-700 rounded-full mb-3 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: sentimentColor }}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 font-mono">
        <span>-1.0</span>
        <span>+1.0</span>
      </div>
    </KpiCard>
  );
};

// Card 3: Ally Relationships
const AllyRelationshipsCard = ({
  data,
}: {
  data: { allyCount?: number; partnerCount?: number };
}) => {
  const allyCount = data?.allyCount || 14;
  const partnerCount = data?.partnerCount || 23;
  const total = allyCount + partnerCount;

  const donutData = [
    { name: 'ALLY', value: allyCount, color: RELATIONSHIP_COLORS.ALLY },
    { name: 'PARTNER', value: partnerCount, color: RELATIONSHIP_COLORS.PARTNER },
  ];

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <Users className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">Müttefik Ağları</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-lg font-semibold text-emerald-400 font-mono">{allyCount} ALLY</span>
        <span className="text-gray-500">+</span>
        <span className="text-lg font-semibold text-blue-400 font-mono">
          {partnerCount} PARTNER
        </span>
      </div>
      <div className="text-xs text-gray-400 mb-3">●●●●●●●●●●●○○○○ {total} total</div>
      <ResponsiveContainer width="100%" height={60}>
        <PieChart>
          <Pie
            data={donutData}
            cx="50%"
            cy="50%"
            innerRadius={18}
            outerRadius={28}
            paddingAngle={2}
            dataKey="value"
          >
            {donutData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--bg-secondary)',
              border: 'var(--border-subtle)',
              borderRadius: 4,
              fontSize: 11,
              color: 'var(--text-primary)',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </KpiCard>
  );
};

// Card 4: Risk Index
const RiskIndexCard = ({ data }: { data: { adversaryCount?: number; cautiousCount?: number } }) => {
  const adversaryCount = data?.adversaryCount || 2;
  const cautiousCount = data?.cautiousCount || 18;
  const riskLevel =
    adversaryCount + cautiousCount < 10
      ? 'DÜŞÜK'
      : adversaryCount + cautiousCount < 20
        ? 'ORTA'
        : 'YÜKSEK';
  const riskColor =
    riskLevel === 'DÜŞÜK' ? '#10b981' : riskLevel === 'ORTA' ? '#f59e0b' : '#ef4444';
  const riskProgress = riskLevel === 'DÜŞÜK' ? 20 : riskLevel === 'ORTA' ? 50 : 80;

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">Risk Endeksi</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-semibold font-mono" style={{ color: riskColor }}>
          {adversaryCount + cautiousCount}
        </span>
        <span className="text-xs" style={{ color: riskColor }}>
          {riskLevel}
        </span>
      </div>
      <div className="text-xs text-gray-400 mb-3">
        ADVERSARY: {adversaryCount} | CAUTIOUS: {cautiousCount}
      </div>
      <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: riskColor }}
          initial={{ width: 0 }}
          animate={{ width: `${riskProgress}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
    </KpiCard>
  );
};

// Card 5: Dominant Emotion (NEW)
const DominantEmotionCard = ({
  data,
}: {
  data: {
    dominantEmotion?: string;
    sessionCount?: number;
    emotionDistribution?: Record<string, number>;
  };
}) => {
  const dominantEmotion = data?.dominantEmotion || 'cooperative';
  const sessionCount = data?.sessionCount || 12;

  const emotionDistribution = data?.emotionDistribution || {
    cooperative: 40,
    constructive: 25,
    neutral_cautious: 20,
    concerned: 15,
  };

  const maxCount = Math.max(...(Object.values(emotionDistribution) as number[]));

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <Zap className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">Baskın Duygu</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-xl font-semibold text-gray-100 capitalize">{dominantEmotion}</span>
        <span className="text-xs text-gray-400">{sessionCount} oturum</span>
      </div>
      <div className="space-y-1.5">
        {Object.entries(emotionDistribution).map(([emotion, count]: [string, unknown]) => {
          const percentage = ((count as number) / maxCount) * 100;
          const colors: Record<string, string> = {
            cooperative: '#10b981',
            constructive: '#3b82f6',
            neutral_cautious: '#6b7280',
            concerned: '#f59e0b',
          };
          return (
            <div key={emotion} className="flex items-center gap-2">
              <span className="text-[10px] text-gray-400 w-16 truncate">{emotion}</span>
              <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: colors[emotion] || '#6b7280' }}
                  initial={{ width: 0 }}
                  animate={{ width: `${percentage}%` }}
                  transition={{ duration: 0.6, delay: 0.1 }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </KpiCard>
  );
};

// Card 6: Active Sessions (NEW)
const ActiveSessionsCard = ({
  data,
}: {
  data: {
    sessionCount?: number;
    highestSession?: { name: string; sentiment: number };
    lowestSession?: { name: string; sentiment: number };
  };
}) => {
  const sessionCount = data?.sessionCount || 12;
  const highestSession = data?.highestSession || { name: 'Erdoğan', sentiment: 0.31 };
  const lowestSession = data?.lowestSession || { name: 'Lavrov', sentiment: 0.08 };

  return (
    <KpiCard>
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp className="w-4 h-4 text-indigo-400" />
        <span className="text-xs text-gray-400 uppercase tracking-wider">
          Analiz Edilen Oturumlar
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-2xl font-semibold text-gray-100 font-mono">
          <AnimatedNumber value={sessionCount} />
        </span>
        <span className="text-xs text-gray-400">oturum</span>
      </div>
      <div className="space-y-1.5 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-400">En yüksek:</span>
          <span className="text-gray-200">
            {highestSession.name}{' '}
            <span className="font-mono text-green-400">+{highestSession.sentiment.toFixed(2)}</span>
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">En düşük:</span>
          <span className="text-gray-200">
            {lowestSession.name}{' '}
            <span className="font-mono text-gray-400">+{lowestSession.sentiment.toFixed(2)}</span>
          </span>
        </div>
      </div>
    </KpiCard>
  );
};

export const VizKpiCards = () => {
  const { data } = useVizStore();

  // Calculate metrics from vizStore data
  const metrics = useMemo(() => {
    const { countryNodes, bilateralFlows, sessionTimeline } = data;

    const totalInteractions = bilateralFlows.reduce((sum, flow) => sum + flow.interactionCount, 0);
    const activePairs = bilateralFlows.length;

    const avgSentiment =
      bilateralFlows.length > 0
        ? bilateralFlows.reduce((sum, flow) => sum + flow.avgSentiment, 0) / bilateralFlows.length
        : 0;

    const allyCount = bilateralFlows.filter((f) => f.relationshipType === 'ALLY').length;
    const partnerCount = bilateralFlows.filter((f) => f.relationshipType === 'PARTNER').length;
    const adversaryCount = bilateralFlows.filter((f) => f.relationshipType === 'ADVERSARY').length;
    const cautiousCount = bilateralFlows.filter((f) => f.relationshipType === 'CAUTIOUS').length;

    // Calculate dominant emotion from country nodes
    const emotionCounts: Record<string, number> = {
      cooperative: 0,
      constructive: 0,
      neutral_cautious: 0,
      concerned: 0,
    };

    countryNodes.forEach((node) => {
      if (node.dominantEmotion) {
        emotionCounts[node.dominantEmotion] = (emotionCounts[node.dominantEmotion] || 0) + 1;
      }
    });

    const dominantEmotion =
      Object.entries(emotionCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'neutral_cautious';

    // Session sentiment stats
    const highestSession = sessionTimeline.reduce(
      (max, s) => (s.avgSentiment > max.avgSentiment ? s : max),
      sessionTimeline[0] || { sessionLabel: 'N/A', avgSentiment: 0 },
    );
    const lowestSession = sessionTimeline.reduce(
      (min, s) => (s.avgSentiment < min.avgSentiment ? s : min),
      sessionTimeline[0] || { sessionLabel: 'N/A', avgSentiment: 0 },
    );

    return {
      totalInteractions,
      activePairs,
      trend: 12, // Mock trend - would need historical data
      avgSentiment,
      allyCount,
      partnerCount,
      adversaryCount,
      cautiousCount,
      dominantEmotion,
      sessionCount: sessionTimeline.length,
      emotionDistribution: emotionCounts,
      highestSession: { name: highestSession.sessionLabel, sentiment: highestSession.avgSentiment },
      lowestSession: { name: lowestSession.sessionLabel, sentiment: lowestSession.avgSentiment },
    };
  }, [data]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <TotalInteractionsCard data={metrics} />
      <AverageSentimentCard data={metrics} />
      <AllyRelationshipsCard data={metrics} />
      <RiskIndexCard data={metrics} />
      <DominantEmotionCard data={metrics} />
      <ActiveSessionsCard data={metrics} />
    </div>
  );
};
