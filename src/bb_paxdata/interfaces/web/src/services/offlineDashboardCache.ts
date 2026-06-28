import type {
  BilateralSentimentData,
  ConsensusDistribution,
  DailyTrend,
  FormulaHealth,
  KpiStats,
  PriorityDistribution,
  TriggerDistribution,
} from '@/types';

const DB_NAME = 'bb-paxdata-dashboard-cache';
const DB_VERSION = 1;
const STORE_NAME = 'dashboard_snapshot';
const CACHE_KEY = 'latest';
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;

export interface DashboardSnapshot {
  kpi: KpiStats;
  formulaHealth: FormulaHealth[];
  dailyTrend: DailyTrend[];
  priorityDist: PriorityDistribution[];
  triggerDist: TriggerDistribution[];
  consensusDist: ConsensusDistribution[];
  bilateral: BilateralSentimentData[];
  savedAt: string;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'key' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error('IndexedDB dashboard cache açılamadı'));
  });
}

export async function saveDashboardSnapshot(
  snapshot: Omit<DashboardSnapshot, 'savedAt'>,
): Promise<void> {
  const database = await openDatabase();

  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    transaction.oncomplete = () => {
      database.close();
      resolve();
    };
    transaction.onerror = () => {
      database.close();
      reject(transaction.error ?? new Error('Dashboard cache yazılamadı'));
    };

    store.put({
      key: CACHE_KEY,
      ...snapshot,
      savedAt: new Date().toISOString(),
    });
  });
}

export async function readDashboardSnapshot(): Promise<DashboardSnapshot | null> {
  const database = await openDatabase();

  try {
    const snapshot = await new Promise<DashboardSnapshot | null>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(CACHE_KEY);

      transaction.oncomplete = () => database.close();
      transaction.onerror = () => {
        database.close();
        reject(transaction.error ?? new Error('Dashboard cache okunamadı'));
      };

      request.onsuccess = () => {
        const result = request.result as (DashboardSnapshot & { key?: string }) | undefined;
        if (!result) {
          resolve(null);
          return;
        }

        resolve({
          kpi: result.kpi,
          formulaHealth: result.formulaHealth,
          dailyTrend: result.dailyTrend,
          priorityDist: result.priorityDist,
          triggerDist: result.triggerDist,
          consensusDist: result.consensusDist,
          bilateral: result.bilateral ?? [],
          savedAt: result.savedAt,
        });
      };

      request.onerror = () => reject(request.error ?? new Error('Dashboard cache okunamadı'));
    });

    if (!snapshot) {
      return null;
    }

    const ageMs = Date.now() - new Date(snapshot.savedAt).getTime();
    if (Number.isFinite(ageMs) && ageMs <= CACHE_TTL_MS) {
      return snapshot;
    }

    return null;
  } finally {
    database.close();
  }
}
