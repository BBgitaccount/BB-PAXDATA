import { clsx } from 'clsx';
import { Pause, Play, RotateCcw, Zap } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface StreamData {
  item_id: string;
  priority: number;
  data: {
    content?: string;
    type?: string;
    [key: string]: unknown;
  };
}

interface StreamingResultProps {
  sessionId: string;
  wsUrl?: string;
  className?: string;
}

type StreamSpeed = 1 | 2 | 4;

export function StreamingResult({
  sessionId,
  wsUrl = `ws://localhost:8000/api/ws/analysis/${sessionId}`,
  className,
}: StreamingResultProps) {
  const [sentences, setSentences] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [speed, setSpeed] = useState<StreamSpeed>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [buffer, setBuffer] = useState<StreamData[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const displayIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Split text into sentences
  const splitIntoSentences = (text: string): string[] => {
    return text.match(/[^.!?]+[.!?]+/g) || [text];
  };

  // Adjust display interval based on speed
  useEffect(() => {
    // Process new data from buffer
    const processBuffer = () => {
      if (isPaused || buffer.length === 0) return;

      const item = buffer[0];
      const content = item.data.content;

      if (content) {
        const newSentences = splitIntoSentences(content);
        setSentences((prev) => [...prev, ...newSentences]);
      }

      setBuffer((prev) => prev.slice(1));
    };

    if (displayIntervalRef.current) {
      clearInterval(displayIntervalRef.current);
    }

    const interval = 1000 / speed;
    displayIntervalRef.current = setInterval(processBuffer, interval);

    return () => {
      if (displayIntervalRef.current) {
        clearInterval(displayIntervalRef.current);
      }
    };
  }, [speed, isPaused, buffer]);

  // WebSocket connection
  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setIsLoading(false);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'analysis_result':
          setBuffer((prev) => [...prev, message]);
          break;
        case 'stream_paused':
          setIsPaused(true);
          break;
        case 'stream_resumed':
          setIsPaused(false);
          break;
        case 'rewind_results': {
          const rewindSentences = message.results.flatMap((r: StreamData) =>
            r.data.content ? splitIntoSentences(r.data.content) : [],
          );
          setSentences(rewindSentences);
          break;
        }
        case 'connected':
          console.log('Stream connected');
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
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
  }, [sessionId, wsUrl]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [sentences]);

  const handlePause = () => {
    setIsPaused(!isPaused);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: isPaused ? 'resume' : 'pause' }));
    }
  };

  const handleRewind = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'rewind', count: 5 }));
    }
  };

  const handleSpeedChange = (newSpeed: StreamSpeed) => {
    setSpeed(newSpeed);
  };

  if (isLoading) {
    return <StreamingSkeleton />;
  }

  return (
    <div className={clsx('bg-white rounded-lg shadow-sm border border-gray-200', className)}>
      {/* Header with controls */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div
            className={clsx('w-2 h-2 rounded-full', isConnected ? 'bg-green-500' : 'bg-red-500')}
          />
          <span className="text-sm font-medium text-gray-700">Analysis Stream</span>
          <span className="text-xs text-gray-500">({sentences.length} sentences)</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Speed control */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            {[1, 2, 4].map((s) => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s as StreamSpeed)}
                className={clsx(
                  'px-2 py-1 text-xs font-medium rounded transition-colors',
                  speed === s
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900',
                )}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Pause/Resume */}
          <button
            onClick={handlePause}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title={isPaused ? 'Resume' : 'Pause'}
          >
            {isPaused ? (
              <Play className="w-4 h-4 text-gray-700" />
            ) : (
              <Pause className="w-4 h-4 text-gray-700" />
            )}
          </button>

          {/* Rewind */}
          <button
            onClick={handleRewind}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Rewind last 5 sentences"
          >
            <RotateCcw className="w-4 h-4 text-gray-700" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div ref={containerRef} className="h-96 overflow-y-auto p-4 space-y-2">
        {sentences.length === 0 ? (
          <div className="text-center text-gray-500 py-8">Waiting for analysis results...</div>
        ) : (
          sentences.map((sentence, index) => (
            <div
              key={index}
              className="animate-fade-in p-2 rounded bg-gray-50 hover:bg-gray-100 transition-colors"
              style={{
                animationDelay: `${index * 50}ms`,
              }}
            >
              <p className="text-sm text-gray-800 leading-relaxed">{sentence}</p>
            </div>
          ))
        )}

        {/* Buffer indicator */}
        {buffer.length > 0 && !isPaused && (
          <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
            <Zap className="w-3 h-3" />
            <span>{buffer.length} items in buffer</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Skeleton loader component
function StreamingSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header skeleton */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-gray-300 animate-pulse" />
          <div className="h-4 w-32 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="flex items-center gap-2">
          <div className="h-8 w-24 bg-gray-200 rounded-lg animate-pulse" />
          <div className="h-8 w-8 bg-gray-200 rounded-lg animate-pulse" />
          <div className="h-8 w-8 bg-gray-200 rounded-lg animate-pulse" />
        </div>
      </div>

      {/* Content skeleton */}
      <div className="h-96 p-4 space-y-2">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="h-16 bg-gray-100 rounded animate-pulse"
            style={{ animationDelay: `${i * 100}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
