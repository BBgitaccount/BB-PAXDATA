// frontend/src/pwa/offlineVerdictQueue.ts
import { openDB, IDBPDatabase } from 'idb';

export interface OfflineVerdict {
  sentenceId: string;
  reviewerId: string;
  verdict: 'approved' | 'rejected' | 'escalated';
  customNotes?: string;
  timestamp: number;
}

const DB_NAME = 'PaxdataOfflineStore';
const STORE_NAME = 'verdict_queue';
const DB_VERSION = 1;

export class OfflineVerdictQueue {
  private dbPromise: Promise<IDBPDatabase>;

  constructor() {
    this.dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db: IDBPDatabase) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, {
            keyPath: 'sentenceId',
            autoIncrement: false,
          });
        }
      },
    });
  }

  /**
   * Add a verdict to the offline synchronization queue.
   */
  async enqueueVerdict(verdict: OfflineVerdict): Promise<void> {
    const db = await this.dbPromise;
    await db.put(STORE_NAME, verdict);
  }

  /**
   * Retrieve all verdicts currently queued in the offline store.
   */
  async getAllQueued(): Promise<OfflineVerdict[]> {
    const db = await this.dbPromise;
    return await db.getAll(STORE_NAME);
  }

  /**
   * Delete a verdict from the queue once successfully synced.
   */
  async dequeueVerdict(sentenceId: string): Promise<void> {
    const db = await this.dbPromise;
    await db.delete(STORE_NAME, sentenceId);
  }

  /**
   * Clear all queued items.
   */
  async clearQueue(): Promise<void> {
    const db = await this.dbPromise;
    await db.clear(STORE_NAME);
  }
}

/**
 * Sync offline verdicts when network connection is restored.
 */
export async function syncOfflineVerdicts(
  queue: OfflineVerdictQueue,
  apiClient: {
    submitVerdict: (payload: {
      sentence_id: string;
      reviewer_id: string;
      verdict: string;
      notes?: string;
      timestamp: number;
    }) => Promise<void>;
  }
): Promise<void> {
  const pending = await queue.getAllQueued();

  for (const verdict of pending) {
    try {
      await apiClient.submitVerdict({
        sentence_id: verdict.sentenceId,
        reviewer_id: verdict.reviewerId,
        verdict: verdict.verdict,
        notes: verdict.customNotes,
        timestamp: verdict.timestamp,
      });

      // Remove from queue upon successful submission
      await queue.dequeueVerdict(verdict.sentenceId);
    } catch (error) {
      console.error(`Sync failed for sentence: ${verdict.sentenceId}`, error);
      // Conflict protocol: If server rejects due to validation error (e.g. locks or stale data),
      // we log it and keep the local queue intact or implement custom resolution.
    }
  }
}
