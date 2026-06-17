import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
          <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{
              fill: '#8A8A8A',
              fontSize: 10,
              fontFamily: 'JetBrains Mono',
            }}
            axisLine={{ stroke: '#2A2A2A' }}
            tickLine={false}
            angle={-25}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tick={{
              fill: '#8A8A8A',
              fontSize: 10,
              fontFamily: 'JetBrains Mono',
            }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#161616',
              border: '0.5px solid #2A2A2A',
              borderRadius: 0,
              fontSize: 12,
              fontFamily: 'JetBrains Mono',
              color: '#F5F5F5',
            }}
            cursor={{ fill: 'rgba(255,255,255,0.02)' }}
          />
          <Bar
            dataKey="fpRate"
            name="False Positive %"
            fill="#5C2626"
            stroke="#5C2626"
            strokeWidth={1}
            barSize={16}
          />
          <Bar
            dataKey="corrRate"
            name="Correction %"
            fill="#5C4A26"
            stroke="#5C4A26"
            strokeWidth={1}
            barSize={16}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
