import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/useToast';
import { syncQueuedVerdicts } from '@/services/offlineVerdictQueue';
import { useReviewQueueStore } from '@/store/reviewQueueStore';

let initialSyncAttempted = false;

export function useOfflineVerdictQueueSync(): void {
  const queryClient = useQueryClient();
  const toast = useToast();
  const confirmVerdict = useReviewQueueStore((state) => state.confirmVerdict);
  const syncingRef = useRef(false);

  useEffect(() => {
    const runSync = async () => {
      if (syncingRef.current || (typeof navigator !== 'undefined' && navigator.onLine === false)) {
        return;
      }

      syncingRef.current = true;
      try {
        const result = await syncQueuedVerdicts((payload) => {
          confirmVerdict(payload.log_id);
        });

        if (result.syncedCount > 0) {
          void queryClient.invalidateQueries({ queryKey: ['fail-queue'] });
          void queryClient.invalidateQueries({
            queryKey: ['dashboard-overview'],
          });
          toast.success(`${result.syncedCount} çevrimdışı karar senkronize edildi.`);
        }
      } catch {
        toast.error('Çevrimdışı kararlar senkronize edilemedi.');
      } finally {
        syncingRef.current = false;
      }
    };

    if (!initialSyncAttempted) {
      initialSyncAttempted = true;
      void runSync();
    }

    const handleOnline = () => {
      void runSync();
    };

    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [confirmVerdict, queryClient, toast]);
}
