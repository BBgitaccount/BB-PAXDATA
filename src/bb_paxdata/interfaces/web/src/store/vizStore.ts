// src/bb_paxdata/interfaces/web/src/store/vizStore.ts

import { create } from 'zustand';
import {
  getBilateralFlows,
  getCountryNodes,
  getCountryRiskProfile,
  getSentimentMatrix,
  getSessionTimeline,
} from '../api/visualizationApi';
import type {
  BilateralFlow,
  CountryNode,
  CountryRiskProfile,
  ReferenceContext,
  ReferenceFlow,
  RelationshipType,
  SentimentMatrix,
  SessionTimeline,
} from '../types/visualization';

export interface VizFilters {
  selectedSessions: string[]; // empty = all
  selectedRelTypes: RelationshipType[]; // empty = all
  selectedContexts: ReferenceContext[]; // empty = all
  minInteractions: number; // default: 2
  minAffinity: number; // default: -1.0
  highlightedCountry: string | null; // hover/click
  selectedCountry: string | null; // drawer open
}

export interface VizData {
  countryNodes: CountryNode[];
  bilateralFlows: BilateralFlow[];
  sentimentMatrix: SentimentMatrix | null;
  sessionTimeline: SessionTimeline[];
  referenceFlows: ReferenceFlow[];
}

export interface VizState {
  filters: VizFilters;
  data: VizData;
  loading: Record<string, boolean>;
  errors: Record<string, string | null>;
  activeTab: 'choropleth' | 'network' | 'chord' | 'sankey' | 'heatmap' | 'timeline';
  panelWidth: number; // side panel width in pixels
  isSidePanelOpen: boolean; // side panel visibility toggle

  // Actions:
  setFilter: <K extends keyof VizFilters>(key: K, value: VizFilters[K]) => void;
  resetFilters: () => void;
  fetchAllData: () => Promise<void>;
  fetchCountryProfile: (country: string) => Promise<CountryRiskProfile>;
  setActiveTab: (tab: VizState['activeTab']) => void;
  setHighlightedCountry: (country: string | null) => void;
  setSelectedCountry: (country: string | null) => void;
  setPanelWidth: (width: number) => void;
  toggleSidePanel: (open?: boolean) => void;
}

const DEFAULT_FILTERS: VizFilters = {
  selectedSessions: [],
  selectedRelTypes: [],
  selectedContexts: [],
  minInteractions: 2,
  minAffinity: -1.0,
  highlightedCountry: null,
  selectedCountry: null,
};

const DEFAULT_DATA: VizData = {
  countryNodes: [],
  bilateralFlows: [],
  sentimentMatrix: null,
  sessionTimeline: [],
  referenceFlows: [],
};

export const useVizStore = create<VizState>((set, get) => ({
  filters: { ...DEFAULT_FILTERS },
  data: { ...DEFAULT_DATA },
  loading: {},
  errors: {},
  activeTab: 'choropleth',
  panelWidth: 340,
  isSidePanelOpen: true,

  setFilter: (key, value) => {
    set((state) => ({
      filters: {
        ...state.filters,
        [key]: value,
      },
    }));
  },

  resetFilters: () => {
    set({ filters: { ...DEFAULT_FILTERS } });
  },

  fetchAllData: async () => {
    set((state) => ({
      loading: { ...state.loading, fetchAll: true },
      errors: { ...state.errors, fetchAll: null },
    }));

    try {
      const { selectedSessions, selectedRelTypes, minInteractions, minAffinity } = get().filters;

      // Concurrent execution of exactly 4 API requests
      const [nodes, flows, matrix, timeline] = await Promise.all([
        getCountryNodes({
          sessionId: selectedSessions,
          relationshipType: selectedRelTypes,
        }),
        getBilateralFlows({
          sessionId: selectedSessions,
          minInteractions: minInteractions,
          relationshipTypes: selectedRelTypes,
          minAffinity: minAffinity,
        }),
        getSentimentMatrix(),
        getSessionTimeline(),
      ]);

      const isUnknown = (name?: string | null, code?: string | null) => {
        const n = name?.toUpperCase() || '';
        const c = code?.toUpperCase() || '';
        return !n || n === 'UNKNOWN' || n === 'UNK' || !c || c === 'UNKNOWN' || c === 'UNK';
      };

      const filteredNodes = nodes.filter((n) => !isUnknown(n.country, n.isoAlpha3));
      const filteredFlows = flows.filter(
        (f) => !isUnknown(f.fromCountry, f.fromIso3) && !isUnknown(f.toCountry, f.toIso3),
      );

      let filteredMatrix = matrix;
      if (matrix && matrix.countries) {
        const validIndices: number[] = [];
        const validCountries = matrix.countries.filter((c, idx) => {
          const isValid = !isUnknown(c, c);
          if (isValid) {
            validIndices.push(idx);
          }
          return isValid;
        });

        const filter2D = <T>(arr: T[][]) => {
          return validIndices.map((rowIdx) => validIndices.map((colIdx) => arr[rowIdx]?.[colIdx]));
        };

        filteredMatrix = {
          countries: validCountries,
          matrix: filter2D(matrix.matrix),
          interactionMatrix: filter2D(matrix.interactionMatrix),
          relationshipMatrix: filter2D(matrix.relationshipMatrix),
        };
      }

      const filteredTimeline = timeline.map((t) => ({
        ...t,
        countries: t.countries.filter((c) => !isUnknown(c, c)),
        topRelationships: t.topRelationships.filter(
          (r) => !isUnknown(r.from, r.from) && !isUnknown(r.to, r.to),
        ),
      }));

      set((state) => ({
        data: {
          ...state.data,
          countryNodes: filteredNodes,
          bilateralFlows: filteredFlows,
          sentimentMatrix: filteredMatrix,
          sessionTimeline: filteredTimeline,
        },
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set((state) => ({
        errors: {
          ...state.errors,
          fetchAll: message || 'Hata oluştu',
        },
      }));
    } finally {
      set((state) => ({
        loading: { ...state.loading, fetchAll: false },
      }));
    }
  },

  fetchCountryProfile: async (country: string): Promise<CountryRiskProfile> => {
    set((state) => ({
      loading: { ...state.loading, [`profile:${country}`]: true },
      errors: { ...state.errors, [`profile:${country}`]: null },
    }));

    try {
      const profile = await getCountryRiskProfile(country);
      return profile;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set((state) => ({
        errors: {
          ...state.errors,
          [`profile:${country}`]: message || 'Ülke profili yüklenemedi',
        },
      }));
      throw err;
    } finally {
      set((state) => ({
        loading: { ...state.loading, [`profile:${country}`]: false },
      }));
    }
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab });
  },

  setHighlightedCountry: (country) => {
    set((state) => ({
      filters: {
        ...state.filters,
        highlightedCountry: country,
      },
    }));
  },

  setSelectedCountry: (country) => {
    set((state) => ({
      filters: {
        ...state.filters,
        selectedCountry: country,
      },
    }));
  },

  setPanelWidth: (width) => {
    set({ panelWidth: Math.max(320, Math.min(600, width)) }); // Clamp between 320px and 600px
  },

  toggleSidePanel: (open) => {
    set((state) => ({
      isSidePanelOpen: open !== undefined ? open : !state.isSidePanelOpen,
    }));
  },
}));
