// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/SentimentHeatmap.tsx

import type { TooltipProps } from 'recharts';
import {
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { useVizStore } from '../../../store/vizStore';
import { sentimentToColor } from '../../../utils/visualizationHelpers';

interface HeatmapDataPoint {
  country: string;
  session: string;
  sentiment: number;
  interactions: number;
  relationship: string | null;
  x: number;
  y: number;
}

const HeatmapTooltip = ({ active, payload }: TooltipProps<number, string>) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload as HeatmapDataPoint;
    return (
      <div
        className="p-3 rounded shadow-xl"
        style={{
          backgroundColor: 'var(--geoint-deep)',
          border: 'var(--border-subtle)',
          fontFamily: 'var(--font-body)',
          fontSize: '12px',
          minWidth: '200px',
        }}
      >
        <div className="font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
          {data.country} × {data.session}
        </div>
        <div className="space-y-1">
          <div className="flex justify-between">
            <span style={{ color: 'var(--text-tertiary)' }}>Sentiment:</span>
            <span style={{ color: sentimentToColor(data.sentiment), fontWeight: 600 }}>
              {data.sentiment.toFixed(3)}
            </span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: 'var(--text-tertiary)' }}>Etkileşim:</span>
            <span style={{ color: 'var(--text-primary)' }}>{data.interactions}</span>
          </div>
          {data.relationship && (
            <div className="flex justify-between">
              <span style={{ color: 'var(--text-tertiary)' }}>İlişki:</span>
              <span style={{ color: 'var(--text-primary)' }}>{data.relationship}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
  return null;
};

export const SentimentHeatmap = () => {
  const { data } = useVizStore();
  const { sentimentMatrix, sessionTimeline } = data;

  if (!sentimentMatrix || !sentimentMatrix.countries || sentimentMatrix.countries.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-label)' }}
      >
        <div className="text-center">
          <div className="text-4xl mb-4">📊</div>
          <p>Sentiment matrisi yükleniyor...</p>
        </div>
      </div>
    );
  }

  // Process data for heatmap
  const countries = sentimentMatrix.countries;
  const sessions = sessionTimeline.map((s) => s.sessionLabel || s.sessionId);

  const heatmapData: HeatmapDataPoint[] = [];

  countries.forEach((country, countryIdx) => {
    sessions.forEach((session, sessionIdx) => {
      const sentiment = sentimentMatrix.matrix[countryIdx]?.[sessionIdx];
      const interactions = sentimentMatrix.interactionMatrix[countryIdx]?.[sessionIdx] || 0;
      const relationship = sentimentMatrix.relationshipMatrix[countryIdx]?.[sessionIdx];

      if (sentiment !== null && sentiment !== undefined) {
        heatmapData.push({
          country,
          session,
          sentiment,
          interactions,
          relationship,
          x: sessionIdx,
          y: countryIdx,
        });
      }
    });
  });

  if (heatmapData.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-label)' }}
      >
        <div className="text-center">
          <div className="text-4xl mb-4">📊</div>
          <p>Gösterilecek veri bulunamadı</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full p-4">
      <div className="mb-4">
        <h3
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
        >
          Ülke × Oturum Sentiment Matrisi
        </h3>
        <p
          className="text-sm mt-1"
          style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
        >
          Her ülkenin her oturumdaki ortalama sentiment skoru
        </p>
      </div>

      <div style={{ height: 'calc(100% - 80px)' }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 30, bottom: 80, left: 120 }}>
            <XAxis
              type="number"
              dataKey="x"
              name="Oturum"
              domain={[-0.5, sessions.length - 0.5]}
              tickFormatter={(val) => sessions[val]?.substring(0, 15) || ''}
              tick={{
                fill: 'var(--text-tertiary)',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border-subtle)' }}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Ülke"
              domain={[-0.5, countries.length - 0.5]}
              tickFormatter={(val) => countries[val] || ''}
              tick={{
                fill: 'var(--text-tertiary)',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border-subtle)' }}
              interval={0}
              width={100}
            />
            <ZAxis type="number" dataKey="interactions" range={[30, 100]} />
            <Tooltip
              content={<HeatmapTooltip />}
              cursor={{ strokeDasharray: '3 3', stroke: 'var(--signal-info)' }}
            />
            <Scatter data={heatmapData} shape="square">
              {heatmapData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={sentimentToColor(entry.sentiment)}
                  stroke="var(--geoint-void)"
                  strokeWidth={1}
                  style={{ opacity: 0.8 }}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded"
            style={{ backgroundColor: 'var(--sentiment-adversary)' }}
          />
          <span
            className="text-xs"
            style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
          >
            Negatif (-1.0)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded"
            style={{ backgroundColor: 'var(--sentiment-neutral)' }}
          />
          <span
            className="text-xs"
            style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
          >
            Nötr (0.0)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: 'var(--sentiment-ally)' }} />
          <span
            className="text-xs"
            style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
          >
            Pozitif (+1.0)
          </span>
        </div>
      </div>
    </div>
  );
};
