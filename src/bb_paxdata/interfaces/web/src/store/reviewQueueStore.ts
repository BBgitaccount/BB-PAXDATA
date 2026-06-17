import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface OptimisticVerdictSnapshot {
  logId: number;
  wasHidden: boolean;
}

interface ReviewQueueState {
  hiddenLogIds: number[];
  applyOptimisticVerdict: (logId: number) => OptimisticVerdictSnapshot;
  rollbackOptimisticVerdict: (snapshot: OptimisticVerdictSnapshot) => void;
  confirmVerdict: (logId: number) => void;
}

export const useReviewQueueStore = create<ReviewQueueState>()(
  persist(
    (set, get) => ({
      hiddenLogIds: [],
      applyOptimisticVerdict: (logId) => {
        const wasHidden = get().hiddenLogIds.includes(logId);

        if (!wasHidden) {
          set({ hiddenLogIds: [...get().hiddenLogIds, logId] });
        }

        return { logId, wasHidden };
      },
      rollbackOptimisticVerdict: (snapshot) => {
        if (!snapshot.wasHidden) {
          set({
            hiddenLogIds: get().hiddenLogIds.filter((id) => id !== snapshot.logId),
          });
        }
      },
      confirmVerdict: (logId) => {
        set({ hiddenLogIds: get().hiddenLogIds.filter((id) => id !== logId) });
      },
    }),
    {
      name: 'bb-paxdata-review-queue',
      partialize: (state) => ({ hiddenLogIds: state.hiddenLogIds }),
    },
  ),
);
