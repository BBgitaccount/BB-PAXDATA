import { Activity, AlertTriangle, Clock, Globe, Network, TrendingUp } from 'lucide-react';
import React from 'react';
import { useVizStore } from '../../../store/vizStore';

export const KPIRow: React.FC = () => {
  const { data, filters } = useVizStore();
  const { countryNodes, bilateralFlows, sessionTimeline } = data;
  const { selectedSessions } = filters;

  // Calculate KPIs
  const totalCountries = countryNodes.length;
  const totalConnections = bilateralFlows.length;
  const activeSessions =
    selectedSessions.length > 0 ? selectedSessions.length : sessionTimeline.length;

  // Calculate average sentiment
  const avgSentiment =
    countryNodes.length > 0
      ? countryNodes.reduce((sum, node) => sum + node.avgSentiment, 0) / countryNodes.length
      : 0;

  // Count high-risk relationships (adversary)
  const highRiskConnections = bilateralFlows.filter((f) => f.affinityScore < -0.5).length;

  // Total mentions across all countries
  const totalMentions = countryNodes.reduce((sum, node) => sum + node.totalInteractions, 0);

  const kpis = [
    {
      label: 'Aktif Ülkeler',
      value: totalCountries,
      icon: Globe,
      color: 'var(--signal-info)',
      trend: null,
    },
    {
      label: 'İlişki Hattı',
      value: totalConnections,
      icon: Network,
      color: 'var(--sentiment-partner)',
      trend: null,
    },
    {
      label: 'Oturumlar',
      value: activeSessions,
      icon: Clock,
      color: 'var(--sentiment-neutral)',
      trend: null,
    },
    {
      label: 'Ort. Sentiment',
      value: avgSentiment.toFixed(2),
      icon: TrendingUp,
      color:
        avgSentiment > 0.3
          ? 'var(--sentiment-ally)'
          : avgSentiment < -0.3
            ? 'var(--sentiment-adversary)'
            : 'var(--sentiment-neutral)',
      trend: avgSentiment > 0 ? '+' : '',
    },
    {
      label: 'Risk Noktası',
      value: highRiskConnections,
      icon: AlertTriangle,
      color: 'var(--sentiment-adversary)',
      trend: null,
    },
    {
      label: 'Toplam Mansiyon',
      value: totalMentions.toLocaleString(),
      icon: Activity,
      color: 'var(--text-primary)',
      trend: null,
    },
  ];

  return (
    <div
      className="px-1 py-0.5"
      style={{ backgroundColor: 'var(--geoint-base)', borderBottom: 'var(--border-subtle)' }}
    >
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-1">
        {kpis.map((kpi, index) => {
          const Icon = kpi.icon;
          return (
            <div
              key={index}
              className="p-1 rounded transition-colors"
              style={{
                backgroundColor: 'var(--geoint-deep)',
                border: 'var(--border-subtle)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--geoint-deep)';
              }}
            >
              <div className="flex items-center gap-0.5 mb-0">
                <Icon className="w-2.5 h-2.5" style={{ color: kpi.color }} />
                <div className="geoint-data-label text-[9px]">{kpi.label}</div>
              </div>
              <div className="geoint-data-value text-[10px]" style={{ color: kpi.color }}>
                {kpi.trend}
                {kpi.value}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
