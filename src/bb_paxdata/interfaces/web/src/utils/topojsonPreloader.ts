// src/bb_paxdata/interfaces/web/src/utils/topojsonPreloader.ts
// TopoJSON preloading utility to cache world map geometry data

const TOPOJSON_URL = '/world-110m.json';
const CACHE_DURATION = 86400000; // 24 hours in milliseconds

interface TopoJSONCache {
  data: Record<string, unknown>;
  timestamp: number;
}

let cachedData: TopoJSONCache | null = null;
let preloadPromise: Promise<Record<string, unknown>> | null = null;

/**
 * Preload TopoJSON data and cache it in memory
 */
export const preloadTopoJSON = async (): Promise<Record<string, unknown>> => {
  // Return cached data if still valid
  if (cachedData && Date.now() - cachedData.timestamp < CACHE_DURATION) {
    return cachedData.data;
  }

  // Return existing promise if preload is in progress
  if (preloadPromise) {
    return preloadPromise;
  }

  // Fetch and cache the data
  preloadPromise = fetch(TOPOJSON_URL)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load TopoJSON: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      cachedData = {
        data,
        timestamp: Date.now(),
      };
      preloadPromise = null;
      return data;
    })
    .catch((error) => {
      preloadPromise = null;
      console.error('TopoJSON preload error:', error);
      throw error;
    });

  return preloadPromise;
};

/**
 * Get cached TopoJSON data or fetch if not available
 */
export const getTopoJSON = async (): Promise<Record<string, unknown>> => {
  if (cachedData && Date.now() - cachedData.timestamp < CACHE_DURATION) {
    return cachedData.data;
  }
  return preloadTopoJSON();
};

/**
 * Clear the TopoJSON cache (useful for testing or manual refresh)
 */
export const clearTopoJSONCache = (): void => {
  cachedData = null;
  preloadPromise = null;
};

/**
 * Preload TopoJSON on app initialization
 * Call this in your app entry point (e.g., main.tsx or App.tsx)
 */
export const initTopoJSONPreload = (): void => {
  // Start preloading in the background without blocking
  preloadTopoJSON().catch((error) => {
    console.warn('Background TopoJSON preload failed:', error);
  });
};
