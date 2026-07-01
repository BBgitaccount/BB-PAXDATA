import { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { FormulaHealth } from '@/types';

interface FormulaHealthChartProps {
  data: FormulaHealth[];
}

export const FormulaHealthChart = ({ data }: FormulaHealthChartProps) => {
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        name: d.formula_name.replace(/_/g, ' '),
        fpRate: d.false_positive_rate * 100,
        corrRate: d.correction_rate * 100,
        total: d.total_fail,
      })),
    [data],
  );

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{
              fill: 'var(--text-secondary)',
              fontSize: 10,
              fontFamily: 'JetBrains Mono',
            }}
            axisLine={{ stroke: 'var(--border-hair)' }}
            tickLine={false}
            angle={-25}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tick={{
              fill: 'var(--text-secondary)',
              fontSize: 10,
              fontFamily: 'JetBrains Mono',
            }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--bg-tertiary)',
              border: '0.5px solid var(--border-hair)',
              borderRadius: 0,
              fontSize: 12,
              fontFamily: 'JetBrains Mono',
              color: 'var(--text-primary)',
            }}
            cursor={{ fill: 'rgba(255,255,255,0.02)' }}
          />
          <Bar
            dataKey="fpRate"
            name="False Positive %"
            fill="var(--signal-fail)"
            stroke="var(--signal-fail)"
            strokeWidth={1}
            barSize={16}
          />
          <Bar
            dataKey="corrRate"
            name="Correction %"
            fill="var(--signal-warn)"
            stroke="var(--signal-warn)"
            strokeWidth={1}
            barSize={16}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
