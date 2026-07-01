/**
 * FormulaHealthTrendChart.tsx
 *
 * Renders a multi-line chart showing the daily false-positive rate (%)
 * per formula over a configurable time window.
 *
 * Data source: GET /api/v1/dashboard/formulas/health/trend?days=30
 */
import { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FormulaTrendData {
  date: string;
  formula_name: string;
  fail_count: number;
  false_positive_count: number;
  false_positive_rate: number; // 0.0 – 1.0
}

interface ChartRow {
  date: string;
  [formulaName: string]: number | string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PALETTE = ['#A83232', '#A88B32', '#32A862', '#3262A8', '#8532A8', '#32A8A8', '#A83280'];

// ─── Component ────────────────────────────────────────────────────────────────

interface FormulaHealthTrendChartProps {
  data: FormulaTrendData[];
  /** Title override */
  title?: string;
}

export const FormulaHealthTrendChart = ({
  data,
  title = 'Formül False Positive Oranı — Zamansal Trend (%)',
}: FormulaHealthTrendChartProps) => {
  // Pivot flat array into date-keyed rows for Recharts (memoized for performance)
  const groupedData = useMemo(
    () =>
      data.reduce<ChartRow[]>((acc, item) => {
        let row = acc.find((d) => d.date === item.date);
        if (!row) {
          row = { date: item.date };
          acc.push(row);
        }
        // Store as percentage, 2 decimal places
        row[item.formula_name] = +(item.false_positive_rate * 100).toFixed(2);
        return acc;
      }, []),
    [data],
  );

  const uniqueFormulas = useMemo(
    () => Array.from(new Set(data.map((d) => d.formula_name))),
    [data],
  );
  const isEmpty = data.length === 0;

  return (
    <div className="h-80 bg-carbon-900 border border-carbon-550 p-6 rounded-none">
      <h3 className="text-sm font-semibold text-carbon-50 mb-4">{title}</h3>

      {isEmpty ? (
        <div className="flex items-center justify-center h-56 text-carbon-500 text-xs font-mono">
          Henüz veri yok. Formül başarısızlıkları kaydedildiğinde grafik oluşacak.
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={groupedData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                axisLine={{ stroke: 'var(--border-hair)' }}
                tickLine={false}
                tickFormatter={(v: string) => v.slice(5)} // Show MM-DD only
              />
              <YAxis
                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                unit="%"
                domain={[0, 100]}
                width={36}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-tertiary)',
                  border: '0.5px solid var(--border-hair)',
                  color: 'var(--text-primary)',
                  fontSize: 11,
                  borderRadius: 0,
                }}
                formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                labelStyle={{ color: 'var(--text-secondary)', marginBottom: 4 }}
              />
              <Legend
                verticalAlign="top"
                height={36}
                wrapperStyle={{ fontSize: 10, color: 'var(--text-secondary)' }}
              />
              {uniqueFormulas.map((formula, idx) => (
                <Line
                  key={formula}
                  type="monotone"
                  dataKey={formula}
                  stroke={PALETTE[idx % PALETTE.length]}
                  strokeWidth={1.5}
                  dot={{ r: 2, strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
