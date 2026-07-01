// src/bb_paxdata/interfaces/web/src/pages/BilateralRelations/components/BilateralCountryDrawer.tsx

import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertTriangle,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Clock,
  TrendingUp,
  Users,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getCountryRiskProfile } from '../../../api/visualizationApi';
import type {
  BilateralFlow,
  CountryNode,
  CountryRiskProfile,
  RelationshipType,
  SessionTimeline,
} from '../../../types/visualization';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BilateralCountryDrawerProps {
  country: string | null;
  onClose: () => void;
  /** Optional supplementary data from the viz store to enrich tabs */
  bilateralFlows?: BilateralFlow[];
  countryNodes?: CountryNode[];
  sessionTimeline?: SessionTimeline[];
}

type TabId = 'summary' | 'relations' | 'sessions' | 'trend';

interface RadarDataPoint {
  subject: string;
  value: number;
  fullMark: number;
}

type SortKey = 'country' | 'interactions' | 'sentiment' | 'affinity' | 'relType';
type SortDir = 'asc' | 'desc';

// ─── Constants ────────────────────────────────────────────────────────────────

const RELATIONSHIP_ORDER: RelationshipType[] = [
  'ALLY',
  'PARTNER',
  'NEUTRAL',
  'CAUTIOUS',
  'ADVERSARY',
];

const REL_LABELS: Record<RelationshipType, string> = {
  ALLY: 'ALLY',
  PARTNER: 'PARTNER',
  NEUTRAL: 'NEUTRAL',
  CAUTIOUS: 'CAUTIOUS',
  ADVERSARY: 'ADVERSARY',
};

const CONTEXT_COLORS = {
  PRAISE: '#10b981',
  NEUTRAL_MENTION: '#6b7280',
  ACCUSATION: '#ef4444',
};

// ─── Helper: risk score ────────────────────────────────────────────────────────

function computeRiskScore(profile: CountryRiskProfile): {
  score: number;
  level: 'LOW' | 'MEDIUM' | 'HIGH';
  filledBlocks: number;
  color: string;
} {
  // 0–4 points from accusation ratio
  const accusationPts = profile.accusationRatio * 4;
  // 0–4 points from sentiment (negative = risky)
  const sentimentPts = (1 - (profile.avgSentiment + 1) / 2) * 4;
  // 0–2 points from adversary count (capped at 5 adversaries)
  const adversaryPts = Math.min(profile.adversaryCount / 5, 1) * 2;
  const score = Math.min(10, accusationPts + sentimentPts + adversaryPts);

  let level: 'LOW' | 'MEDIUM' | 'HIGH';
  let color: string;
  if (score >= 7) {
    level = 'HIGH';
    color = '#ef4444';
  } else if (score >= 4) {
    level = 'MEDIUM';
    color = '#f59e0b';
  } else {
    level = 'LOW';
    color = '#10b981';
  }

  const filledBlocks = Math.round((score / 10) * 10);
  return { score, level, filledBlocks, color };
}

// ─── Helper: build radar data ──────────────────────────────────────────────────

function buildRadarData(
  profile: CountryRiskProfile,
  countryNode: CountryNode | undefined,
  allNodes: CountryNode[],
  allFlows: BilateralFlow[],
): RadarDataPoint[] {
  // 1. Sentiment: normalize [-1, 1] -> [0, 100]
  const sentimentScore = Math.max(0, Math.min(100, ((profile.avgSentiment + 1) / 2) * 100));

  // 2. Etki Gücü (Power): powerLevel * 100
  const powerScore = countryNode ? Math.max(0, Math.min(100, countryNode.powerLevel * 100)) : 50;

  // 3. Aktivite (Activity): totalInteractions normalized relative to max
  const maxInteractions = Math.max(...allNodes.map((n) => n.totalInteractions), 1);
  const activityScore = countryNode
    ? Math.max(0, Math.min(100, (countryNode.totalInteractions / maxInteractions) * 100))
    : 0;

  // 4. Kooperatiflik: (1 - accusation_ratio) * 100
  const cooperativenessScore = Math.max(0, Math.min(100, (1 - profile.accusationRatio) * 100));

  // 5. Ağ Merkeziliği: distinct country connections normalized to max degree
  const countryConnections = new Set<string>();
  allFlows.forEach((f) => {
    if (f.fromCountry === profile.country) countryConnections.add(f.toCountry);
    if (f.toCountry === profile.country) countryConnections.add(f.fromCountry);
  });
  const degree = countryConnections.size;

  // Compute max degree across all countries
  const degreeMap = new Map<string, Set<string>>();
  allFlows.forEach((f) => {
    if (!degreeMap.has(f.fromCountry)) degreeMap.set(f.fromCountry, new Set());
    if (!degreeMap.has(f.toCountry)) degreeMap.set(f.toCountry, new Set());
    degreeMap.get(f.fromCountry)!.add(f.toCountry);
    degreeMap.get(f.toCountry)!.add(f.fromCountry);
  });
  const maxDegree = Math.max(...Array.from(degreeMap.values()).map((s) => s.size), 1);
  const centralityScore = Math.max(0, Math.min(100, (degree / maxDegree) * 100));

  return [
    { subject: 'Sentiment', value: Math.round(sentimentScore), fullMark: 100 },
    { subject: 'Etki Gücü', value: Math.round(powerScore), fullMark: 100 },
    { subject: 'Aktivite', value: Math.round(activityScore), fullMark: 100 },
    { subject: 'Kooperatiflik', value: Math.round(cooperativenessScore), fullMark: 100 },
    { subject: 'Ağ Merkeziliği', value: Math.round(centralityScore), fullMark: 100 },
  ];
}

// ─── Helper: context distribution ─────────────────────────────────────────────

function buildContextDistribution(countryNode: CountryNode | undefined) {
  if (!countryNode) return null;
  const total = countryNode.praiseCount + countryNode.neutralCount + countryNode.accusationCount;
  if (total === 0) return null;
  return {
    praise: {
      count: countryNode.praiseCount,
      pct: Math.round((countryNode.praiseCount / total) * 100),
    },
    neutral: {
      count: countryNode.neutralCount,
      pct: Math.round((countryNode.neutralCount / total) * 100),
    },
    accusation: {
      count: countryNode.accusationCount,
      pct: Math.round((countryNode.accusationCount / total) * 100),
    },
  };
}

// ─── Skeleton Loader ───────────────────────────────────────────────────────────

function SkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-sm ${className}`}
      style={{ background: 'var(--geoint-border)', opacity: 0.5 }}
    />
  );
}

function DrawerSkeleton() {
  return (
    <div className="p-5 space-y-5">
      <SkeletonBlock className="h-6 w-2/3" />
      <SkeletonBlock className="h-4 w-1/2" />
      <div className="grid grid-cols-2 gap-3 mt-4">
        {[...Array(6)].map((_, i) => (
          <SkeletonBlock key={i} className="h-14" />
        ))}
      </div>
      <SkeletonBlock className="h-48 w-full mt-4" />
      <SkeletonBlock className="h-32 w-full" />
    </div>
  );
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div
      style={{
        background: 'var(--geoint-deep)',
        border: '1px solid var(--geoint-border)',
        padding: '10px 12px',
        borderRadius: 2,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          fontFamily: 'monospace',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          fontFamily: 'monospace',
          marginTop: 4,
          color: color ?? 'var(--text-primary)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ─── Section Header ────────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div
      style={{
        borderLeft: '2px solid var(--text-primary)',
        paddingLeft: 8,
        fontSize: 10,
        fontWeight: 700,
        color: 'var(--text-secondary)',
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        marginBottom: 10,
        marginTop: 20,
      }}
    >
      {title}
    </div>
  );
}

// ─── Risk Bar ─────────────────────────────────────────────────────────────────

function RiskBar({
  filledBlocks,
  totalBlocks = 10,
  color,
  level,
}: {
  filledBlocks: number;
  totalBlocks?: number;
  color: string;
  level: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        {Array.from({ length: totalBlocks }).map((_, idx) => (
          <div
            key={idx}
            style={{
              width: 6,
              height: 12,
              borderRadius: 1,
              backgroundColor: idx < filledBlocks ? color : 'var(--border-hair)',
              transition: 'background-color 0.2s',
            }}
          />
        ))}
      </div>
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color,
          fontFamily: 'monospace',
          letterSpacing: '0.05em',
        }}
      >
        {level}
      </span>
    </div>
  );
}

// ─── Relationship Spectrum Bar ─────────────────────────────────────────────────

function RelationshipSpectrumBar({
  relType,
  count,
  maxCount,
}: {
  relType: RelationshipType;
  count: number;
  maxCount: number;
}) {
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
  const color = RELATIONSHIP_COLORS[relType];
  const barWidth = Math.max(pct, count > 0 ? 3 : 0);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <div
        style={{
          fontSize: 10,
          fontFamily: 'monospace',
          color: color,
          width: 70,
          flexShrink: 0,
          letterSpacing: '0.05em',
        }}
      >
        {relType}
      </div>
      <div
        style={{
          flex: 1,
          background: 'var(--geoint-deep)',
          borderRadius: 1,
          height: 8,
          overflow: 'hidden',
        }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          style={{ height: '100%', background: color, borderRadius: 1 }}
        />
      </div>
      <div
        style={{
          fontSize: 10,
          fontFamily: 'monospace',
          color: 'var(--text-secondary)',
          width: 20,
          textAlign: 'right',
        }}
      >
        {count}
      </div>
    </div>
  );
}

// ─── Context Bar ───────────────────────────────────────────────────────────────

function ContextBar({
  label,
  pct,
  count,
  color,
}: {
  label: string;
  pct: number;
  count: number;
  color: string;
}) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div
          style={{
            flex: 1,
            height: 14,
            background: 'var(--geoint-deep)',
            borderRadius: 1,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.7, ease: 'easeOut', delay: 0.1 }}
            style={{ height: '100%', background: color, opacity: 0.8, borderRadius: 1 }}
          />
        </div>
        <span
          style={{
            fontSize: 10,
            fontFamily: 'monospace',
            color: color,
            minWidth: 120,
            flexShrink: 0,
          }}
        >
          {label} ({pct}%) • {count}
        </span>
      </div>
    </div>
  );
}

// ─── Custom Tooltip for Recharts ──────────────────────────────────────────────

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'var(--geoint-base)',
        border: '1px solid var(--geoint-border)',
        padding: '6px 10px',
        borderRadius: 2,
        fontFamily: 'monospace',
        fontSize: 11,
      }}
    >
      <div style={{ color: 'var(--text-secondary)', marginBottom: 2 }}>{label}</div>
      <div style={{ color: sentimentToColor(payload[0].value), fontWeight: 700 }}>
        Sentiment: {payload[0].value > 0 ? '+' : ''}
        {payload[0].value.toFixed(3)}
      </div>
    </div>
  );
}

// ─── Tab: Summary ──────────────────────────────────────────────────────────────

function TabSummary({
  profile,
  countryNode,
  allNodes,
  allFlows,
  sessionTimeline,
}: {
  profile: CountryRiskProfile;
  countryNode: CountryNode | undefined;
  allNodes: CountryNode[];
  allFlows: BilateralFlow[];
  sessionTimeline: SessionTimeline[];
}) {
  const radarData = buildRadarData(profile, countryNode, allNodes, allFlows);
  const ctxDist = buildContextDistribution(countryNode);

  // Top interactions for this country
  const relatedFlows = allFlows
    .filter((f) => f.fromCountry === profile.country || f.toCountry === profile.country)
    .sort((a, b) => b.interactionCount - a.interactionCount)
    .slice(0, 5);

  // Relationship breakdown
  const breakdown = profile.relationshipBreakdown;
  const maxBreakdownCount = Math.max(...RELATIONSHIP_ORDER.map((r) => breakdown[r] ?? 0), 1);

  // Active sessions for this country from session timeline
  const activeSessions = sessionTimeline.filter((s) =>
    s.countries.some((c) => c.toLowerCase() === profile.country.toLowerCase()),
  );

  const praiseRatio = 1 - profile.accusationRatio - (ctxDist ? ctxDist.neutral.pct / 100 : 0.5);

  return (
    <div>
      {/* KPI Grid */}
      <SectionHeader title="ÖZET" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <KpiCard label="Toplam Etkileşim" value={profile.totalMentions} />
        <KpiCard
          label="Avg Sentiment"
          value={
            profile.avgSentiment >= 0
              ? `+${profile.avgSentiment.toFixed(3)}`
              : profile.avgSentiment.toFixed(3)
          }
          color={sentimentToColor(profile.avgSentiment)}
        />
        <KpiCard
          label="Konuşmacı Sent."
          value={
            profile.sentimentAsSpeaker >= 0
              ? `+${profile.sentimentAsSpeaker.toFixed(3)}`
              : profile.sentimentAsSpeaker.toFixed(3)
          }
          color={sentimentToColor(profile.sentimentAsSpeaker)}
        />
        <KpiCard
          label="Hedef Sent."
          value={
            profile.sentimentAsTarget >= 0
              ? `+${profile.sentimentAsTarget.toFixed(3)}`
              : profile.sentimentAsTarget.toFixed(3)
          }
          color={sentimentToColor(profile.sentimentAsTarget)}
        />
        <KpiCard label="Müttefik" value={profile.allyCount} color="#10b981" />
        <KpiCard
          label="Düşman"
          value={profile.adversaryCount}
          color={profile.adversaryCount > 0 ? '#ef4444' : '#6b7280'}
        />
        <KpiCard
          label="İtham Oranı"
          value={`${Math.round(profile.accusationRatio * 100)}%`}
          color={profile.accusationRatio > 0.3 ? '#ef4444' : '#f59e0b'}
        />
        <KpiCard
          label="Övgü Oranı"
          value={`${Math.round(Math.max(0, praiseRatio) * 100)}%`}
          color="#10b981"
        />
      </div>

      {/* Relationship Spectrum */}
      <SectionHeader title="İLİŞKİ SPEKTRUMU" />
      {RELATIONSHIP_ORDER.map((rel) => (
        <RelationshipSpectrumBar
          key={rel}
          relType={rel}
          count={breakdown[rel] ?? 0}
          maxCount={maxBreakdownCount}
        />
      ))}

      {/* Top 5 Interactions */}
      <SectionHeader title="EN ÇOK ETKİLEŞİM" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {relatedFlows.length === 0 && (
          <div
            style={{
              color: 'var(--text-secondary)',
              fontSize: 11,
              fontFamily: 'monospace',
              padding: '4px 0',
            }}
          >
            Veri yok.
          </div>
        )}
        {relatedFlows.map((flow, i) => {
          const other = flow.fromCountry === profile.country ? flow.toCountry : flow.fromCountry;
          const maxFlowCount = relatedFlows[0]?.interactionCount ?? 1;
          const barPct = Math.max((flow.interactionCount / maxFlowCount) * 100, 2);
          return (
            <div
              key={`${flow.fromCountry}-${flow.toCountry}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--geoint-deep)',
                border: '1px solid var(--geoint-border)',
                padding: '5px 8px',
                borderRadius: 2,
              }}
            >
              <span
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: 10,
                  fontFamily: 'monospace',
                  width: 14,
                }}
              >
                {i + 1}.
              </span>
              <span
                style={{
                  color: 'var(--text-primary)',
                  fontSize: 11,
                  fontFamily: 'monospace',
                  width: 90,
                  flexShrink: 0,
                }}
              >
                {other}
              </span>
              <span
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: 10,
                  fontFamily: 'monospace',
                  width: 24,
                }}
              >
                {flow.interactionCount}
              </span>
              <span
                style={{
                  color:
                    RELATIONSHIP_COLORS[flow.relationshipType as RelationshipType] ?? '#6b7280',
                  fontSize: 9,
                  fontFamily: 'monospace',
                  width: 60,
                  flexShrink: 0,
                }}
              >
                {flow.relationshipType}
              </span>
              <div
                style={{
                  flex: 1,
                  height: 6,
                  background: 'var(--geoint-border)',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${barPct}%` }}
                  transition={{ duration: 0.5, delay: i * 0.05 }}
                  style={{
                    height: '100%',
                    background:
                      RELATIONSHIP_COLORS[flow.relationshipType as RelationshipType] ??
                      'var(--text-secondary)',
                    borderRadius: 1,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Radar Chart */}
      <SectionHeader title="RADAR PROFİLİ" />
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
            <PolarGrid stroke="var(--geoint-border)" />
            <PolarAngleAxis
              dataKey="subject"
              tick={{ fill: 'var(--text-secondary)', fontSize: 9, fontFamily: 'monospace' }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: 'var(--geoint-border)', fontSize: 8 }}
              tickCount={4}
              stroke="var(--geoint-border)"
            />
            <Radar
              name={profile.country}
              dataKey="value"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.25}
              dot={{ r: 3, fill: '#3b82f6', strokeWidth: 0 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Context Distribution */}
      {ctxDist && (
        <>
          <SectionHeader title="BAĞLAM DAĞILIMI" />
          <ContextBar
            label="PRAISE"
            pct={ctxDist.praise.pct}
            count={ctxDist.praise.count}
            color={CONTEXT_COLORS.PRAISE}
          />
          <ContextBar
            label="NEUTRAL"
            pct={ctxDist.neutral.pct}
            count={ctxDist.neutral.count}
            color={CONTEXT_COLORS.NEUTRAL_MENTION}
          />
          <ContextBar
            label="ACCUSATION"
            pct={ctxDist.accusation.pct}
            count={ctxDist.accusation.count}
            color={CONTEXT_COLORS.ACCUSATION}
          />
        </>
      )}

      {/* Active Sessions */}
      {activeSessions.length > 0 && (
        <>
          <SectionHeader title="AKTİF OTURUMLAR" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {activeSessions.slice(0, 5).map((s) => (
              <div
                key={s.sessionId}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'var(--geoint-deep)',
                  border: '1px solid var(--geoint-border)',
                  padding: '5px 8px',
                  borderRadius: 2,
                }}
              >
                <span
                  style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-secondary)' }}
                >
                  • {s.sessionLabel || s.sessionId}
                </span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: 'monospace',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {s.dominantEmotion}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: 'monospace',
                      fontWeight: 700,
                      color: sentimentToColor(s.avgSentiment),
                    }}
                  >
                    {s.avgSentiment >= 0 ? '+' : ''}
                    {s.avgSentiment.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Top Accusers */}
      {profile.topAccusers.length > 0 && (
        <>
          <SectionHeader title="EN ÇOK İTHAM EDEN" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {profile.topAccusers.map((acc, i) => {
              const flow = allFlows.find(
                (f) =>
                  (f.fromCountry === acc.country && f.toCountry === profile.country) ||
                  (f.toCountry === acc.country && f.fromCountry === profile.country),
              );
              return (
                <div
                  key={acc.country}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    background: 'var(--geoint-deep)',
                    border: '1px solid #3b1818',
                    padding: '5px 8px',
                    borderRadius: 2,
                  }}
                >
                  <span
                    style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-primary)' }}
                  >
                    {i + 1}. {acc.country}
                  </span>
                  <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#ef4444' }}>
                    {acc.count} accusation{acc.count > 1 ? 's' : ''}
                    {flow ? `, ${flow.avgSentiment.toFixed(2)}` : ''}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Top Praise Givers */}
      {profile.topPraiseGivers.length > 0 && (
        <>
          <SectionHeader title="EN ÇOK ÖVEN" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {profile.topPraiseGivers.map((pg, i) => {
              const flow = allFlows.find(
                (f) =>
                  (f.fromCountry === pg.country && f.toCountry === profile.country) ||
                  (f.toCountry === pg.country && f.fromCountry === profile.country),
              );
              return (
                <div
                  key={pg.country}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    background: 'var(--geoint-deep)',
                    border: '1px solid #0d2e1a',
                    padding: '5px 8px',
                    borderRadius: 2,
                  }}
                >
                  <span
                    style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-primary)' }}
                  >
                    {i + 1}. {pg.country}
                  </span>
                  <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#10b981' }}>
                    {pg.count} praise{pg.count > 1 ? 's' : ''}
                    {flow ? `, +${Math.abs(flow.avgSentiment).toFixed(2)}` : ''}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Tab: Relations ────────────────────────────────────────────────────────────

function TabRelations({ country, allFlows }: { country: string; allFlows: BilateralFlow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('interactions');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [search, setSearch] = useState('');
  const [filterRel, setFilterRel] = useState<RelationshipType | 'ALL'>('ALL');

  const relatedFlows = allFlows.filter((f) => f.fromCountry === country || f.toCountry === country);

  const filtered = relatedFlows
    .filter((f) => {
      const other = f.fromCountry === country ? f.toCountry : f.fromCountry;
      const matchSearch = other.toLowerCase().includes(search.toLowerCase());
      const matchRel = filterRel === 'ALL' || f.relationshipType === filterRel;
      return matchSearch && matchRel;
    })
    .sort((a, b) => {
      const otherA = a.fromCountry === country ? a.toCountry : a.fromCountry;
      const otherB = b.fromCountry === country ? b.toCountry : b.fromCountry;
      let cmp = 0;
      switch (sortKey) {
        case 'country':
          cmp = otherA.localeCompare(otherB);
          break;
        case 'interactions':
          cmp = a.interactionCount - b.interactionCount;
          break;
        case 'sentiment':
          cmp = a.avgSentiment - b.avgSentiment;
          break;
        case 'affinity':
          cmp = a.affinityScore - b.affinityScore;
          break;
        case 'relType':
          cmp = a.relationshipType.localeCompare(b.relationshipType);
          break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return null;
    return sortDir === 'desc' ? (
      <ChevronDown style={{ width: 10, height: 10, display: 'inline', marginLeft: 2 }} />
    ) : (
      <ChevronUp style={{ width: 10, height: 10, display: 'inline', marginLeft: 2 }} />
    );
  };

  const thStyle: React.CSSProperties = {
    padding: '5px 6px',
    fontSize: 9,
    fontFamily: 'monospace',
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    cursor: 'pointer',
    userSelect: 'none',
    textAlign: 'left' as const,
    borderBottom: '1px solid var(--geoint-border)',
    whiteSpace: 'nowrap' as const,
  };

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Ülke ara..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1,
            minWidth: 120,
            background: 'var(--geoint-deep)',
            border: '1px solid var(--geoint-border)',
            color: 'var(--text-primary)',
            padding: '5px 8px',
            borderRadius: 2,
            fontSize: 11,
            fontFamily: 'monospace',
            outline: 'none',
          }}
        />
        <select
          value={filterRel}
          onChange={(e) => setFilterRel(e.target.value as RelationshipType | 'ALL')}
          style={{
            background: 'var(--geoint-deep)',
            border: '1px solid var(--geoint-border)',
            color: 'var(--text-secondary)',
            padding: '5px 8px',
            borderRadius: 2,
            fontSize: 11,
            fontFamily: 'monospace',
            outline: 'none',
          }}
        >
          <option value="ALL">Tümü</option>
          {RELATIONSHIP_ORDER.map((r) => (
            <option key={r} value={r}>
              {REL_LABELS[r]}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle} onClick={() => handleSort('country')}>
                Ülke <SortIcon k="country" />
              </th>
              <th style={thStyle} onClick={() => handleSort('relType')}>
                İlişki <SortIcon k="relType" />
              </th>
              <th
                style={{ ...thStyle, textAlign: 'right' as const }}
                onClick={() => handleSort('interactions')}
              >
                Etk. <SortIcon k="interactions" />
              </th>
              <th
                style={{ ...thStyle, textAlign: 'right' as const }}
                onClick={() => handleSort('sentiment')}
              >
                Sent. <SortIcon k="sentiment" />
              </th>
              <th
                style={{ ...thStyle, textAlign: 'right' as const }}
                onClick={() => handleSort('affinity')}
              >
                Affinity <SortIcon k="affinity" />
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    padding: '12px 6px',
                    textAlign: 'center',
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    fontFamily: 'monospace',
                  }}
                >
                  Sonuç bulunamadı.
                </td>
              </tr>
            )}
            {filtered.map((flow) => {
              const other = flow.fromCountry === country ? flow.toCountry : flow.fromCountry;
              const relColor =
                RELATIONSHIP_COLORS[flow.relationshipType as RelationshipType] ?? '#6b7280';
              return (
                <tr
                  key={`${flow.fromCountry}-${flow.toCountry}`}
                  style={{ borderBottom: '1px solid var(--geoint-base)' }}
                >
                  <td
                    style={{
                      padding: '5px 6px',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      color: 'var(--text-primary)',
                    }}
                  >
                    {other}
                  </td>
                  <td
                    style={{
                      padding: '5px 6px',
                      fontSize: 9,
                      fontFamily: 'monospace',
                      color: relColor,
                    }}
                  >
                    {flow.relationshipType}
                  </td>
                  <td
                    style={{
                      padding: '5px 6px',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      color: 'var(--text-secondary)',
                      textAlign: 'right',
                    }}
                  >
                    {flow.interactionCount}
                  </td>
                  <td
                    style={{
                      padding: '5px 6px',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      color: sentimentToColor(flow.avgSentiment),
                      textAlign: 'right',
                    }}
                  >
                    {flow.avgSentiment >= 0 ? '+' : ''}
                    {flow.avgSentiment.toFixed(3)}
                  </td>
                  <td
                    style={{
                      padding: '5px 6px',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      color: sentimentToColor(flow.affinityScore),
                      textAlign: 'right',
                    }}
                  >
                    {flow.affinityScore >= 0 ? '+' : ''}
                    {flow.affinityScore.toFixed(3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div
        style={{
          marginTop: 8,
          fontSize: 10,
          fontFamily: 'monospace',
          color: 'var(--text-tertiary)',
          textAlign: 'right',
        }}
      >
        {filtered.length} / {relatedFlows.length} kayıt
      </div>
    </div>
  );
}

// ─── Tab: Sessions ─────────────────────────────────────────────────────────────

function TabSessions({
  country,
  sessionTimeline,
}: {
  country: string;
  sessionTimeline: SessionTimeline[];
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const activeSessions = sessionTimeline.filter((s) =>
    s.countries.some((c) => c.toLowerCase() === country.toLowerCase()),
  );

  if (activeSessions.length === 0) {
    return (
      <div
        style={{
          padding: '24px 0',
          textAlign: 'center',
          fontSize: 12,
          fontFamily: 'monospace',
          color: 'var(--text-tertiary)',
        }}
      >
        Bu ülke için aktif oturum bulunamadı.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {activeSessions.map((s) => {
        const isOpen = expandedId === s.sessionId;
        return (
          <div
            key={s.sessionId}
            style={{
              background: 'var(--geoint-deep)',
              border: '1px solid var(--geoint-border)',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpandedId(isOpen ? null : s.sessionId)}
              style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 10px',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Clock
                  style={{ width: 12, height: 12, color: 'var(--text-secondary)', flexShrink: 0 }}
                />
                <span
                  style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-secondary)' }}
                >
                  {s.sessionLabel || s.sessionId}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: 'monospace',
                    color: sentimentToColor(s.avgSentiment),
                    fontWeight: 700,
                  }}
                >
                  {s.avgSentiment >= 0 ? '+' : ''}
                  {s.avgSentiment.toFixed(3)}
                </span>
                {isOpen ? (
                  <ChevronUp style={{ width: 12, height: 12, color: 'var(--text-secondary)' }} />
                ) : (
                  <ChevronDown style={{ width: 12, height: 12, color: 'var(--text-secondary)' }} />
                )}
              </div>
            </button>

            {/* Expanded content */}
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{ overflow: 'hidden', borderTop: '1px solid var(--geoint-border)' }}
                >
                  <div style={{ padding: '10px 10px 12px' }}>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 8,
                        marginBottom: 10,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            textTransform: 'uppercase',
                          }}
                        >
                          Baskın Duygu
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--text-primary)',
                            fontFamily: 'monospace',
                            marginTop: 2,
                          }}
                        >
                          {s.dominantEmotion}
                        </div>
                      </div>
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            textTransform: 'uppercase',
                          }}
                        >
                          Ülkeler
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            marginTop: 2,
                          }}
                        >
                          {s.countries.slice(0, 5).join(', ')}
                          {s.countries.length > 5 ? '…' : ''}
                        </div>
                      </div>
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            textTransform: 'uppercase',
                          }}
                        >
                          Övgü
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: '#10b981',
                            fontFamily: 'monospace',
                            marginTop: 2,
                          }}
                        >
                          {s.praiseCount}
                        </div>
                      </div>
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            textTransform: 'uppercase',
                          }}
                        >
                          İtham
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: '#ef4444',
                            fontFamily: 'monospace',
                            marginTop: 2,
                          }}
                        >
                          {s.accusationCount}
                        </div>
                      </div>
                    </div>
                    {s.topRelationships.length > 0 && (
                      <div>
                        <div
                          style={{
                            fontSize: 9,
                            color: 'var(--text-secondary)',
                            fontFamily: 'monospace',
                            textTransform: 'uppercase',
                            marginBottom: 4,
                          }}
                        >
                          Top İlişkiler
                        </div>
                        {s.topRelationships.slice(0, 3).map((r, i) => (
                          <div
                            key={i}
                            style={{
                              fontSize: 10,
                              fontFamily: 'monospace',
                              color: 'var(--text-secondary)',
                              padding: '2px 0',
                              borderTop: i > 0 ? '1px solid var(--geoint-base)' : 'none',
                            }}
                          >
                            {r.from} →{' '}
                            <span style={{ color: RELATIONSHIP_COLORS[r.type] ?? '#6b7280' }}>
                              {r.type}
                            </span>
                            → {r.to}
                            <span style={{ color: sentimentToColor(r.score), marginLeft: 6 }}>
                              {r.score >= 0 ? '+' : ''}
                              {r.score.toFixed(2)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

// ─── Tab: Trend ────────────────────────────────────────────────────────────────

function TabTrend({
  country,
  sessionTimeline,
}: {
  country: string;
  sessionTimeline: SessionTimeline[];
}) {
  const activeSessions = sessionTimeline
    .filter((s) => s.countries.some((c) => c.toLowerCase() === country.toLowerCase()))
    .sort((a, b) => {
      if (a.createdAt && b.createdAt) return a.createdAt.localeCompare(b.createdAt);
      return a.sessionId.localeCompare(b.sessionId);
    });

  if (activeSessions.length < 2) {
    return (
      <div
        style={{
          padding: '48px 0',
          textAlign: 'center',
          fontSize: 12,
          fontFamily: 'monospace',
          color: 'var(--text-tertiary)',
        }}
      >
        <TrendingUp
          style={{ width: 32, height: 32, color: 'var(--geoint-border)', margin: '0 auto 12px' }}
        />
        <div>Trend için en az 2 oturum gerekli.</div>
      </div>
    );
  }

  const chartData = activeSessions.map((s) => ({
    name: (s.sessionLabel || s.sessionId).slice(0, 15),
    sentiment: s.avgSentiment,
  }));

  const minVal = Math.min(...chartData.map((d) => d.sentiment));
  const maxVal = Math.max(...chartData.map((d) => d.sentiment));
  const padding = Math.max(0.05, (maxVal - minVal) * 0.15);

  return (
    <div>
      <SectionHeader title="SENTIMENT TRENDİ" />
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
            <defs>
              <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--geoint-border)" opacity={0.5} />
            <XAxis
              dataKey="name"
              tick={{ fill: 'var(--text-secondary)', fontSize: 8, fontFamily: 'monospace' }}
              axisLine={{ stroke: 'var(--geoint-border)' }}
              tickLine={false}
              angle={-30}
              textAnchor="end"
              interval={0}
            />
            <YAxis
              domain={[minVal - padding, maxVal + padding]}
              tick={{ fill: 'var(--text-secondary)', fontSize: 8, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => v.toFixed(2)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="sentiment"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#sentGrad)"
              dot={{ r: 3, fill: '#3b82f6', strokeWidth: 0 }}
              activeDot={{ r: 5, fill: '#60a5fa' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Stats summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
        <KpiCard label="Min Sentiment" value={minVal.toFixed(3)} color={sentimentToColor(minVal)} />
        <KpiCard label="Max Sentiment" value={maxVal.toFixed(3)} color={sentimentToColor(maxVal)} />
        <KpiCard
          label="Değişim"
          value={
            ((chartData[chartData.length - 1]?.sentiment ?? 0) - (chartData[0]?.sentiment ?? 0) >= 0
              ? '+'
              : '') +
            (
              (chartData[chartData.length - 1]?.sentiment ?? 0) - (chartData[0]?.sentiment ?? 0)
            ).toFixed(3)
          }
          color={sentimentToColor(
            (chartData[chartData.length - 1]?.sentiment ?? 0) - (chartData[0]?.sentiment ?? 0),
          )}
        />
      </div>
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export function BilateralCountryDrawer({
  country,
  onClose,
  bilateralFlows = [],
  countryNodes = [],
  sessionTimeline = [],
}: BilateralCountryDrawerProps) {
  const [profile, setProfile] = useState<CountryRiskProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('summary');
  const abortRef = useRef<AbortController | null>(null);

  // ESC to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Fetch profile when country changes
  useEffect(() => {
    if (!country) {
      setProfile(null);
      setError(null);
      return;
    }

    // Cancel previous request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setProfile(null);
    setActiveTab('summary');

    getCountryRiskProfile(country, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setProfile(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err?.message ?? 'Bilinmeyen hata');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [country]);

  const countryNode = countryNodes.find(
    (n) =>
      n.country.toLowerCase() === (country ?? '').toLowerCase() ||
      (n.isoAlpha3 ?? '').toLowerCase() === (country ?? '').toLowerCase(),
  );

  const tabs: Array<{
    id: TabId;
    label: string;
    Icon: React.ComponentType<{ style?: React.CSSProperties }>;
  }> = [
    { id: 'summary', label: 'Özet', Icon: BarChart2 },
    { id: 'relations', label: 'İlişkiler', Icon: Users },
    { id: 'sessions', label: 'Oturumlar', Icon: Clock },
    { id: 'trend', label: 'Trend', Icon: TrendingUp },
  ];

  return (
    <AnimatePresence>
      {country && (
        <>
          {/* Backdrop */}
          <motion.div
            key="drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              backdropFilter: 'blur(4px)',
              WebkitBackdropFilter: 'blur(4px)',
              background: 'rgba(0,0,0,0.45)',
              zIndex: 40,
            }}
          />

          {/* Drawer panel */}
          <motion.div
            key="drawer-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: 'min(440px, 100vw)',
              background: 'var(--geoint-base)',
              borderLeft: '1px solid var(--geoint-border)',
              zIndex: 50,
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-8px 0 40px rgba(0,0,0,0.6)',
            }}
          >
            {/* ── Sticky Header ─────────────────────────────────────────── */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                padding: '16px 18px 12px',
                borderBottom: '1px solid var(--geoint-border)',
                background: 'var(--geoint-base)',
                flexShrink: 0,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 9,
                    fontFamily: 'monospace',
                    color: 'var(--text-secondary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.15em',
                    marginBottom: 4,
                  }}
                >
                  ▶ COUNTRY INTELLIGENCE
                </div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    fontFamily: 'monospace',
                    color: 'var(--text-primary)',
                    letterSpacing: '0.04em',
                    lineHeight: 1.2,
                  }}
                >
                  {country?.toUpperCase()}
                </div>
                {profile && !loading && (
                  <div style={{ marginTop: 6 }}>
                    <div
                      style={{
                        fontSize: 9,
                        color: 'var(--text-secondary)',
                        fontFamily: 'monospace',
                        marginBottom: 3,
                      }}
                    >
                      Risk Seviyesi:
                    </div>
                    <RiskBar {...computeRiskScore(profile)} />
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Drawer'ı kapat"
                style={{
                  background: 'transparent',
                  border: '1px solid var(--geoint-border)',
                  color: 'var(--text-secondary)',
                  width: 30,
                  height: 30,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  borderRadius: 2,
                  flexShrink: 0,
                  transition: 'border-color 0.15s, color 0.15s',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor =
                    'var(--text-secondary)';
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--geoint-border)';
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-secondary)';
                }}
              >
                <X style={{ width: 14, height: 14 }} />
              </button>
            </div>

            {/* ── Tab Navigation ─────────────────────────────────────────── */}
            <div
              style={{
                display: 'flex',
                borderBottom: '1px solid var(--geoint-border)',
                background: 'var(--geoint-void)',
                flexShrink: 0,
              }}
            >
              {tabs.map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 3,
                      padding: '8px 4px',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                      color: isActive ? '#60a5fa' : 'var(--text-tertiary)',
                      cursor: 'pointer',
                      transition: 'color 0.15s, border-color 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive)
                        (e.currentTarget as HTMLButtonElement).style.color =
                          'var(--text-secondary)';
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive)
                        (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-tertiary)';
                    }}
                  >
                    <tab.Icon style={{ width: 13, height: 13 }} />
                    <span style={{ fontSize: 9, fontFamily: 'monospace', letterSpacing: '0.08em' }}>
                      {tab.label}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* ── Scrollable Body ─────────────────────────────────────────── */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '12px 16px 24px',
                scrollbarWidth: 'thin',
                scrollbarColor: 'var(--geoint-border) var(--geoint-void)',
              }}
            >
              {/* Loading */}
              {loading && <DrawerSkeleton />}

              {/* Error */}
              {!loading && error && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 12,
                    padding: '48px 0',
                    textAlign: 'center',
                  }}
                >
                  <AlertTriangle style={{ width: 32, height: 32, color: '#ef4444' }} />
                  <div style={{ fontSize: 12, fontFamily: 'monospace', color: '#ef4444' }}>
                    Veri yüklenemedi.
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      fontFamily: 'monospace',
                      color: 'var(--text-secondary)',
                      maxWidth: 260,
                    }}
                  >
                    {error}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      // Re-trigger fetch by toggling loading
                      setError(null);
                      setLoading(true);
                      const controller = new AbortController();
                      abortRef.current = controller;
                      getCountryRiskProfile(country!, controller.signal)
                        .then(setProfile)
                        .catch((err) => setError(err?.message ?? 'Hata'))
                        .finally(() => setLoading(false));
                    }}
                    style={{
                      padding: '6px 16px',
                      background: 'transparent',
                      border: '1px solid #3b82f6',
                      color: '#60a5fa',
                      fontSize: 11,
                      fontFamily: 'monospace',
                      cursor: 'pointer',
                      borderRadius: 2,
                    }}
                  >
                    Tekrar Dene
                  </button>
                </div>
              )}

              {/* Tab Content */}
              {!loading && !error && profile && (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                  >
                    {activeTab === 'summary' && (
                      <TabSummary
                        profile={profile}
                        countryNode={countryNode}
                        allNodes={countryNodes}
                        allFlows={bilateralFlows}
                        sessionTimeline={sessionTimeline}
                      />
                    )}
                    {activeTab === 'relations' && (
                      <TabRelations country={profile.country} allFlows={bilateralFlows} />
                    )}
                    {activeTab === 'sessions' && (
                      <TabSessions country={profile.country} sessionTimeline={sessionTimeline} />
                    )}
                    {activeTab === 'trend' && (
                      <TabTrend country={profile.country} sessionTimeline={sessionTimeline} />
                    )}
                  </motion.div>
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
