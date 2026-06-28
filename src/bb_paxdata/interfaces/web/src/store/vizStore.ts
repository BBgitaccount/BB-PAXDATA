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

      set((state) => ({
        data: {
          ...state.data,
          countryNodes: nodes,
          bilateralFlows: flows,
          sentimentMatrix: matrix,
          sessionTimeline: timeline,
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
