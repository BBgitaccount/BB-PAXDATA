/**
 * BuildTUIMonitor.tsx
 *
 * Real-time pipeline build progress monitor over WebSocket.
 * Connects to /api/ws/build and renders a terminal-style dashboard.
 *
 * Features:
 *  - Live progress bar
 *  - Stage and file name tracking
 *  - Scrolling log stream (last 50 lines)
 *  - 25-second heartbeat ping to prevent proxy timeouts
 *  - Connection indicator dot
 */
import { useCallback, useEffect, useRef, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BuildPayload {
  file_name: string;
  processed_files: number;
  total_files: number;
  status: 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'ERROR';
  current_stage: string;
  timestamp?: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_LOGS = 50;
const HEARTBEAT_MS = 25_000;

const STATUS_COLORS: Record<BuildPayload['status'], string> = {
  PROCESSING: 'text-signal-warn animate-[blink-status_2s_ease-in-out_infinite]',
  COMPLETED: 'text-signal-pass',
  FAILED: 'text-signal-fail',
  ERROR: 'text-signal-fail',
};

// ─── Component ────────────────────────────────────────────────────────────────

export type ConnectionState = 'connecting' | 'connected' | 'error' | 'disconnected';

const STATE_DOT_COLORS: Record<ConnectionState, string> = {
  connected: 'bg-signal-pass',
  connecting: 'bg-signal-warn animate-pulse',
  error: 'bg-signal-fail',
  disconnected: 'bg-carbon-600',
};

interface BuildTUIMonitorProps {
  /** Override the WebSocket URL. Defaults to same-host /api/ws/build */
  wsUrl?: string;
}

export const BuildTUIMonitor = ({ wsUrl }: BuildTUIMonitorProps) => {
  const [status, setStatus] = useState<BuildPayload | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [connState, setConnState] = useState<ConnectionState>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Auto-scroll log pane to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = useCallback((msg: string) => {
    setLogs((prev) => [...prev.slice(-(MAX_LOGS - 1)), msg]);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    setConnState('connecting');

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = wsUrl ?? `${proto}//${window.location.host}/api/ws/build`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    let hbInterval: number;

    ws.onopen = () => {
      setConnState('connected');
      reconnectAttempts.current = 0; // reset attempts
      addLog('[system] Build monitor connected.');

      // Heartbeat loop — keeps reverse-proxy from closing idle connections
      hbInterval = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, HEARTBEAT_MS);
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(event.data) as {
          type: string;
          data?: BuildPayload;
        };
        if (msg.type === 'IngestionProgress' && msg.data) {
          const d = msg.data;
          setStatus(d);
          const ts = new Date().toLocaleTimeString();
          addLog(
            `[${ts}] ${d.current_stage}: ${d.file_name || '—'} ` +
              `(${d.processed_files}/${d.total_files})`,
          );
        }
      } catch {
        /* ignore parse errors */
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) return;

      setConnState((prev) => (prev === 'error' ? 'error' : 'disconnected'));
      if (hbInterval) clearInterval(hbInterval);
      addLog('[system] Disconnected from build monitor.');

      // Attempt reconnect if not unmounted and attempts < 3
      if (reconnectAttempts.current < 3) {
        reconnectAttempts.current += 1;
        addLog(`[system] Reconnecting in 5s (Attempt ${reconnectAttempts.current}/3)...`);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 5000);
      }
    };

    ws.onerror = () => {
      if (wsRef.current !== ws) return;

      setConnState('error');
      addLog('[error] WebSocket connection error.');
    };
  }, [wsUrl, addLog]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [connect]);

  // ── Derived values ──────────────────────────────────────────────────────────

  const progressPct =
    status && status.total_files > 0
      ? Math.min(100, (status.processed_files / status.total_files) * 100)
      : 0;

  const isDone = status?.status === 'COMPLETED';
  const hasFailed = status?.status === 'FAILED' || status?.status === 'ERROR';

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="bg-[var(--bg-primary)] border border-[var(--border-hair)] p-6 font-mono rounded-none space-y-4">
      {/* ── Header bar ─────────────────────────────────────────────────────── */}
      <div className="flex justify-between items-center text-xs text-carbon-350 border-b border-carbon-700 pb-2">
        <span className="tracking-widest text-micro uppercase">⚙ Pipeline Build Monitor</span>
        <span className="flex items-center gap-2">
          {/* Connection dot */}
          <span
            className={`h-2 w-2 rounded-full flex-shrink-0 ${STATE_DOT_COLORS[connState]}`}
            title={connState.toUpperCase()}
          />
          {/* Build status label */}
          {status ? (
            <span className={STATUS_COLORS[status.status] ?? 'text-carbon-400'}>
              {status.status}
            </span>
          ) : (
            <span className="text-carbon-500">IDLE</span>
          )}
        </span>
      </div>

      {/* ── Error Banner ────────────────────────────────────────────────────── */}
      {connState === 'error' && (
        <div className="bg-signal-fail/20 border border-signal-fail text-signal-fail px-4 py-2 text-2xs rounded text-center">
          WebSocket bağlantısı kurulamadı — Pipeline monitor devre dışı
        </div>
      )}

      {/* ── Progress bar ────────────────────────────────────────────────────── */}
      {status && (
        <div className="space-y-1">
          <div className="flex justify-between text-2xs text-carbon-400">
            <span>
              {status.processed_files} / {status.total_files} dosya
            </span>
            <span>{progressPct.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-carbon-800 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${
                hasFailed ? 'bg-signal-fail' : isDone ? 'bg-signal-pass' : 'bg-carbon-200'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* ── Current file & stage ─────────────────────────────────────────────── */}
      {status?.file_name && (
        <div className="space-y-0.5">
          <div className="text-2xs text-carbon-500 uppercase tracking-widest">Current Stage</div>
          <div className="text-xs text-carbon-100 truncate">
            <span className="text-carbon-400">[{status.current_stage}]</span> {status.file_name}
          </div>
        </div>
      )}

      {/* ── Log stream ──────────────────────────────────────────────────────── */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border-hair)] rounded-none p-3 h-36 overflow-y-auto text-3xs text-carbon-400 space-y-0.5">
        {logs.length === 0 ? (
          <div className="text-carbon-600 italic">
            {connState === 'connected'
              ? 'Waiting for build activity...'
              : connState === 'connecting'
                ? 'Connecting...'
                : 'Connection failed.'}
          </div>
        ) : (
          logs.map((line, i) => (
            <div
              key={i}
              className={
                line.startsWith('[error]')
                  ? 'text-signal-fail'
                  : line.startsWith('[system]')
                    ? 'text-carbon-500 italic'
                    : ''
              }
            >
              {line}
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* ── No-build idle state ─────────────────────────────────────────────── */}
      {!status && connState === 'connected' && (
        <div className="text-2xs text-carbon-500 font-mono text-center py-2">
          No active build running. Ready to receive pipeline events.
        </div>
      )}
    </div>
  );
};
