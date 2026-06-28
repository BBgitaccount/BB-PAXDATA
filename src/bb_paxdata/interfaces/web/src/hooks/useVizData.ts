// src/bb_paxdata/interfaces/web/src/hooks/useVizData.ts

import { useVizStore } from '../store/vizStore';
import type { BilateralFlow, CountryNode } from '../types/visualization';

/**
 * Returns country nodes that have a valid ISO Alpha-3 code.
 */
export function useCountryNodes(): CountryNode[] {
  const nodes = useVizStore((state) => state.data.countryNodes);
  return nodes.filter((node) => node.isoAlpha3 !== null);
}

/**
 * Returns filtered bilateral flows.
 */
export function useBilateralFlows(): BilateralFlow[] {
  return useVizStore((state) => state.data.bilateralFlows);
}

/**
 * Returns the currently active selected sessions.
 */
export function useActiveSessionData(): string[] {
  return useVizStore((state) => state.filters.selectedSessions);
}

/**
 * Returns statistical indicators for a single country.
 */
export function useCountryStats(country: string): CountryNode | null {
  const nodes = useVizStore((state) => state.data.countryNodes);
  return nodes.find((node) => node.country === country) || null;
}
