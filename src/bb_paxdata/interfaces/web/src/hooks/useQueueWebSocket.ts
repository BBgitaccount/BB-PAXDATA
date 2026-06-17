import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/useToast';

const getWsUrl = () => {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const url = new URL(base);
  const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${url.host}/api/ws/queue`;
};

export function useQueueWebSocket(): void {
  const queryClient = useQueryClient();
  const toast = useToast();
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;

      try {
        const wsUrl = getWsUrl();
        console.log(`Connecting to WebSocket at ${wsUrl}`);
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          console.log('WebSocket connection established.');
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event === 'queue_updated') {
              // Invalidate react-query cache to refresh the UI
              void queryClient.invalidateQueries({ queryKey: ['fail-queue'] });
              void queryClient.invalidateQueries({
                queryKey: ['dashboard-overview'],
              });

              // Display visual toast alert
              toast.info(
                `Kuyruk Güncellendi: LOG-${data.log_id} kararı ${data.verdict} olarak kaydedildi.`,
              );
            } else if (data.event === 'new_flagged_item') {
              // Invalidate react-query cache to refresh the UI
              void queryClient.invalidateQueries({ queryKey: ['fail-queue'] });
              void queryClient.invalidateQueries({
                queryKey: ['dashboard-overview'],
              });

              // Read user-configured threshold
              let threshold = 70;
              const stored = localStorage.getItem('bb_system_settings');
              if (stored) {
                try {
                  const settings = JSON.parse(stored);
                  if (typeof settings.risk_threshold === 'number') {
                    threshold = settings.risk_threshold;
                  }
                } catch {
                  // Ignore parsing error
                }
              }

              const score = typeof data.ai_risk_score === 'number' ? data.ai_risk_score : 0;
              const normalizedScore = score <= 10 ? score * 10 : score;

              if (normalizedScore >= threshold) {
                toast.error(
                  `YÜKSEK RİSK TESPİT EDİLDİ [Skor: ${normalizedScore}%]: ${data.speaker_name || 'Bilinmeyen Aktör'} (${data.country || 'Bilinmeyen Ülke'}): "${data.sentence_text || 'İçerik Yok'}"`,
                );
              } else {
                toast.warning(
                  `Yeni İnceleme Talebi [Skor: ${normalizedScore}%]: ${data.speaker_name || 'Bilinmeyen Aktör'} (${data.country || 'Bilinmeyen Ülke'})`,
                );
              }
            }
          } catch (err) {
            console.error('Error parsing WebSocket message:', err);
          }
        };

        socket.onclose = () => {
          console.log('WebSocket connection closed.');
          if (isMounted) {
            reconnectTimeoutId = setTimeout(connect, 5000);
          }
        };

        socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          socket.close();
        };
      } catch (err) {
        console.error('Failed to create WebSocket:', err);
        if (isMounted) {
          reconnectTimeoutId = setTimeout(connect, 5000);
        }
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutId) {
        clearTimeout(reconnectTimeoutId);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [queryClient, toast]);
}
