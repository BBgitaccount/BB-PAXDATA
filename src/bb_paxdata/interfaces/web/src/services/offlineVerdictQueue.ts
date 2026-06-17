import { apiClient } from '@/services/apiClient';
import type { VerdictPayload, VerdictResponse } from '@/types';

const DB_NAME = 'bb-paxdata-offline';
const DB_VERSION = 1;
const STORE_NAME = 'verdict_queue';

export interface QueuedVerdictEntry {
  id?: number;
  payload: VerdictPayload;
  createdAt: string;
}

export interface SyncVerdictResult {
  syncedCount: number;
  remainingCount: number;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('IndexedDB açılırken hata oluştu'));
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  executor: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  const database = await openDatabase();

  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, mode);
      const store = transaction.objectStore(STORE_NAME);

      transaction.oncomplete = () => database.close();
      transaction.onerror = () => {
        database.close();
        reject(transaction.error ?? new Error('IndexedDB transaction failed'));
      };

      void executor(store).then(resolve).catch(reject);
    });
  } catch (error) {
    database.close();
    throw error;
  }
}

export async function enqueueVerdict(payload: VerdictPayload): Promise<QueuedVerdictEntry> {
  const entry: QueuedVerdictEntry = {
    payload,
    createdAt: new Date().toISOString(),
  };

  return withStore('readwrite', async (store) => {
    const request = store.add(entry);
    return new Promise<QueuedVerdictEntry>((resolve, reject) => {
      request.onsuccess = () => resolve({ ...entry, id: Number(request.result) });
      request.onerror = () =>
        reject(request.error ?? new Error('Karar çevrimdışı kuyruğa eklenemedi'));
    });
  });
}

export async function listQueuedVerdicts(): Promise<QueuedVerdictEntry[]> {
  return withStore('readonly', async (store) => {
    const request = store.getAll();
    return new Promise<QueuedVerdictEntry[]>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result as QueuedVerdictEntry[]);
      request.onerror = () => reject(request.error ?? new Error('Kuyruk okunamadı'));
    });
  });
}

export async function deleteQueuedVerdict(id: number): Promise<void> {
  await withStore('readwrite', async (store) => {
    const request = store.delete(id);
    return new Promise<void>((resolve, reject) => {
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error ?? new Error('Kuyruk kaydı silinemedi'));
    });
  });
}

export async function syncQueuedVerdicts(
  onSynced?: (payload: VerdictPayload) => void,
): Promise<SyncVerdictResult> {
  const queuedEntries = await listQueuedVerdicts();
  const orderedEntries = [...queuedEntries].sort((left, right) => (left.id ?? 0) - (right.id ?? 0));

  let syncedCount = 0;

  for (const entry of orderedEntries) {
    if (entry.id == null) {
      continue;
    }

    await apiClient.post<VerdictResponse>('/api/v1/verdict', entry.payload);

    await deleteQueuedVerdict(entry.id);
    syncedCount += 1;
    onSynced?.(entry.payload);
  }

  const remainingCount = (await listQueuedVerdicts()).length;
  return { syncedCount, remainingCount };
}

export function isOfflineCapableError(error: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return true;
  }

  if (error instanceof TypeError) {
    return true;
  }

  if (error instanceof Error) {
    return /failed to fetch|networkerror|load failed/i.test(error.message);
  }

  return false;
}
