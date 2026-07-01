import { clsx } from 'clsx';
import { Activity, Clock, Database, Wifi } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface StreamMetrics {
  queue_size: number;
  max_queue_size: number;
  utilization: number;
  backpressure_active: boolean;
  total_processed: number;
  total_dropped: number;
  active_sessions: number;
  active_connections: number;
  average_processing_time?: number;
}

interface StreamDashboardProps {
  wsUrl?: string;
  refreshInterval?: number;
  className?: string;
}

export function StreamDashboard({
  wsUrl = 'ws://localhost:8000/api/ws/notifications',
  refreshInterval = 5000,
  className,
}: StreamDashboardProps) {
  const [metrics, setMetrics] = useState<StreamMetrics>({
    queue_size: 0,
    max_queue_size: 1000,
    utilization: 0,
    backpressure_active: false,
    total_processed: 0,
    total_dropped: 0,
    active_sessions: 0,
    active_connections: 0,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [history, setHistory] = useState<
    Array<{ time: string; queue_size: number; utilization: number }>
  >([]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Dashboard WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'metrics_update' || message.event === 'metrics_update') {
        const newMetrics = message.data;
        setMetrics(newMetrics);

        // Update history
        const now = new Date().toLocaleTimeString();
        setHistory((prev) => {
          const newHistory = [
            ...prev,
            {
              time: now,
              queue_size: newMetrics.queue_size,
              utilization: newMetrics.utilization * 100,
            },
          ];
          // Keep last 30 data points
          return newHistory.slice(-30);
        });
      }
    };

    ws.onerror = (error) => {
      console.error('Dashboard WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('Dashboard WebSocket disconnected');
    };

    // Heartbeat
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => {
      clearInterval(heartbeat);
      ws.close();
    };
  }, [wsUrl]);

  // Poll metrics endpoint as fallback
  useEffect(() => {
    if (isConnected) return;

    const pollMetrics = async () => {
      try {
        const response = await fetch('/api/v1/stream/metrics');
        if (response.ok) {
          const data = await response.json();
          setMetrics(data);

          const now = new Date().toLocaleTimeString();
          setHistory((prev) => {
            const newHistory = [
              ...prev,
              {
                time: now,
                queue_size: data.queue_size,
                utilization: data.utilization * 100,
              },
            ];
            return newHistory.slice(-30);
          });
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    pollMetrics();
    const interval = setInterval(pollMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [isConnected, refreshInterval]);

  const MetricCard = ({
    icon: Icon,
    label,
    value,
    unit,
    trend,
    color = 'blue',
  }: {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    value: number;
    unit?: string;
    trend?: number;
    color?: 'blue' | 'green' | 'yellow' | 'red';
  }) => {
    const colorClasses = {
      blue: 'bg-signal-info/10 text-signal-info border-signal-info/20',
      green: 'bg-signal-pass/10 text-signal-pass border-signal-pass/20',
      yellow: 'bg-signal-warn/10 text-signal-warn border-signal-warn/20',
      red: 'bg-signal-fail/10 text-signal-fail border-signal-fail/20',
    };

    return (
      <div className={clsx('p-4 rounded-sharp border border-hair', colorClasses[color])}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5" />
            <span className="text-sm font-medium">{label}</span>
          </div>
          {trend !== undefined && (
            <span className={clsx('text-xs', trend > 0 ? 'text-green-600' : 'text-red-600')}>
              {trend > 0 ? '+' : ''}
              {trend}%
            </span>
          )}
        </div>
        <div className="mt-2">
          <span className="text-2xl font-bold">{value.toLocaleString()}</span>
          {unit && <span className="text-sm ml-1">{unit}</span>}
        </div>
      </div>
    );
  };

  return (
    <div className={clsx('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Stream Dashboard</h2>
          <p className="text-sm text-[var(--text-secondary)]">Real-time streaming metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={clsx(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-signal-pass' : 'bg-signal-fail',
            )}
          />
          <span className="text-sm text-[var(--text-secondary)]">
            {isConnected ? 'Live' : 'Polling'}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={Database}
          label="Queue Size"
          value={metrics.queue_size}
          unit={`/ ${metrics.max_queue_size}`}
          color={metrics.backpressure_active ? 'red' : 'blue'}
        />
        <MetricCard
          icon={Activity}
          label="Processed"
          value={metrics.total_processed}
          color="green"
        />
        <MetricCard
          icon={Wifi}
          label="Active Connections"
          value={metrics.active_connections}
          color="blue"
        />
        <MetricCard
          icon={Clock}
          label="Avg Processing Time"
          value={metrics.average_processing_time || 0}
          unit="ms"
          color="yellow"
        />
      </div>

      {/* Additional Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          icon={Database}
          label="Active Sessions"
          value={metrics.active_sessions}
          color="blue"
        />
        <MetricCard
          icon={Activity}
          label="Dropped Items"
          value={metrics.total_dropped}
          color={metrics.total_dropped > 0 ? 'red' : 'green'}
        />
        <MetricCard
          icon={Activity}
          label="Queue Utilization"
          value={Math.round(metrics.utilization * 100)}
          unit="%"
          color={metrics.utilization > 0.8 ? 'red' : metrics.utilization > 0.5 ? 'yellow' : 'green'}
        />
      </div>

      {/* Queue Size Chart */}
      <div className="card-carbon rounded-sharp p-6">
        <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-4">
          Queue Size Over Time
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={history}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              stroke="var(--border-hair)"
            />
            <YAxis
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--bg-tertiary)',
                border: '0.5px solid var(--border-hair)',
                color: 'var(--text-primary)',
                fontSize: 11,
                borderRadius: 0,
              }}
            />
            <Line
              type="monotone"
              dataKey="queue_size"
              stroke="var(--sentiment-partner)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Utilization Chart */}
      <div className="card-carbon rounded-sharp p-6">
        <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-4">
          Queue Utilization (%)
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={history}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hair)" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              stroke="var(--border-hair)"
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--bg-tertiary)',
                border: '0.5px solid var(--border-hair)',
                color: 'var(--text-primary)',
                fontSize: 11,
                borderRadius: 0,
              }}
            />
            <Line
              type="monotone"
              dataKey="utilization"
              stroke="var(--sentiment-ally)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Backpressure Warning */}
      {metrics.backpressure_active && (
        <div className="bg-signal-fail/10 border border-signal-fail rounded-sharp p-4 text-[var(--text-primary)]">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-signal-fail" />
            <span className="font-medium">Backpressure Active</span>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Queue utilization is at {Math.round(metrics.utilization * 100)}%. High-priority items
            only.
          </p>
        </div>
      )}
    </div>
  );
}
