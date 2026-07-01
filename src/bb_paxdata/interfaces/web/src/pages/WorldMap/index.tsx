// src/bb_paxdata/interfaces/web/src/pages/WorldMap/index.tsx

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Globe, RefreshCw, Zap } from 'lucide-react';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useVizStore } from '../../store/vizStore';
import { sentimentToColor } from '../../utils/visualizationHelpers';
import { WorldMapLayout } from './WorldMapLayout';
import { CountryDrawer } from './components/CountryDrawer';
import { KPIRow } from './components/KPIRow';
import { SidePanelContent } from './components/SidePanelContent';
import { VizCommandBar } from './components/VizCommandBar';
import { VizStoreProvider } from './components/VizStoreProvider';

// Lazy load heavy components for code splitting
const ChoroplethMap = lazy(() =>
  import('./components/ChoroplethMap').then((m) => ({ default: m.ChoroplethMap })),
);

// Skeleton loader component for Suspense fallback
const SkeletonLoader = () => (
  <div
    className="flex items-center justify-center h-full"
    style={{ backgroundColor: 'var(--geoint-void)' }}
  >
    <div className="flex flex-col items-center gap-4">
      <RefreshCw className="w-8 h-8 animate-spin" style={{ color: 'var(--text-tertiary)' }} />
      <span
        className="text-sm"
        style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
      >
        Bileşen yükleniyor...
      </span>
    </div>
  </div>
);

interface CountryConnection {
  from_country: string;
  to_country: string;
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  avg_sentiment: number;
  interaction_count: number;
  relationship_type: string;
  affinity_score: number;
}

const WorldMapContent = () => {
  const [selectedConnection, setSelectedConnection] = useState<CountryConnection | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  // Optimized Zustand selectors - only subscribe to specific fields
  const filters = useVizStore((state) => state.filters);
  const data = useVizStore((state) => state.data);
  const setHighlightedCountry = useVizStore((state) => state.setHighlightedCountry);
  const setSelectedCountryStore = useVizStore((state) => state.setSelectedCountry);
  // Sync local selected country with vizStore
  const selectedCountry = filters.selectedCountry;
  const highlightedCountry = filters.highlightedCountry;

  // Handle close country drawer event
  useEffect(() => {
    const handleCloseDrawer = () => {
      setSelectedCountryStore(null);
    };
    window.addEventListener('close-country-drawer', handleCloseDrawer);
    return () => window.removeEventListener('close-country-drawer', handleCloseDrawer);
  }, [setSelectedCountryStore]);

  // Transform vizStore data to component format for ChoroplethMap
  const { nodes, connections } = useMemo(() => {
    const nodes = data.countryNodes.map((n) => ({
      country_code: n.isoAlpha3 || '',
      country_name: n.country,
      latitude: 0, // Will be computed from geo data
      longitude: 0, // Will be computed from geo data
      total_mentions: n.totalInteractions,
      avg_sentiment: n.avgSentiment,
    }));

    const connections = data.bilateralFlows.map((f) => ({
      from_country: f.fromCountry,
      to_country: f.toCountry,
      from_lat: 0,
      from_lon: 0,
      to_lat: 0,
      to_lon: 0,
      avg_sentiment: f.avgSentiment,
      interaction_count: f.interactionCount,
      relationship_type: f.relationshipType,
      affinity_score: f.affinityScore,
    }));

    return { nodes, connections };
  }, [data]);

  return (
    <WorldMapLayout
      header={
        <div
          className="rounded px-3 py-2"
          style={{
            backgroundColor: 'var(--geoint-deep)',
            border: 'var(--border-subtle)',
          }}
        >
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4" style={{ color: 'var(--signal-info)' }} />
            <span
              className="text-xs font-semibold"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
            >
              Dünya Haritası
            </span>
          </div>
        </div>
      }
      kpiRow={<KPIRow />}
      tabBar={<VizCommandBar mapContainerRef={mapContainerRef} />}
      sidePanelContent={<SidePanelContent />}
      countryDrawer={
        selectedCountry && (
          <CountryDrawer
            country={selectedCountry}
            onClose={() => setSelectedCountryStore(null)}
            bilateralFlows={data.bilateralFlows}
            countryNodes={data.countryNodes}
            sessionTimeline={data.sessionTimeline}
          />
        )
      }
    >
      {/* Connection Details Overlay */}
      {selectedConnection && (
        <div
          className="absolute top-4 left-4 w-72 p-4 shadow-2xl z-20 animate-[fade-in-right_200ms_ease-out]"
          style={{ backgroundColor: 'var(--geoint-base)', border: 'var(--border-subtle)' }}
        >
          <div
            className="flex items-center justify-between mb-3 pb-2"
            style={{ borderBottom: 'var(--border-subtle)' }}
          >
            <h4
              className="text-xs font-semibold flex items-center gap-2"
              style={{ fontFamily: 'var(--font-label)', color: 'var(--text-primary)' }}
            >
              <Zap className="w-3.5 h-3.5" style={{ color: 'var(--signal-info)' }} />
              İLİŞKİ DETAYLARI
            </h4>
            <button
              onClick={() => setSelectedConnection(null)}
              className="text-sm"
              style={{ color: 'var(--text-tertiary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
            >
              ×
            </button>
          </div>
          <div className="space-y-2 text-[11px]">
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                Kaynak:
              </span>
              <span
                className="font-medium"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
              >
                {selectedConnection.from_country}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                Hedef:
              </span>
              <span
                className="font-medium"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
              >
                {selectedConnection.to_country}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                Etkileşim Sayısı:
              </span>
              <span className="font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
                {selectedConnection.interaction_count}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                Ortalama Sentiment:
              </span>
              <span
                className="font-mono font-semibold"
                style={{
                  color: sentimentToColor(selectedConnection.avg_sentiment),
                }}
              >
                {selectedConnection.avg_sentiment.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                İlişki Kategorisi:
              </span>
              <span
                className="font-medium"
                style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}
              >
                {selectedConnection.relationship_type}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}>
                Affinity Skoru:
              </span>
              <span className="font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
                {selectedConnection.affinity_score.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tab Content with Suspense for lazy loading */}
      <Suspense fallback={<SkeletonLoader />}>
        <ChoroplethMap
          nodes={nodes}
          connections={connections}
          setSelectedCountry={setSelectedCountryStore}
          selectedCountry={selectedCountry}
          highlightedCountry={highlightedCountry}
          setHighlightedCountry={setHighlightedCountry}
          selectedConnection={selectedConnection}
          setSelectedConnection={setSelectedConnection}
          mapContainerRef={mapContainerRef}
          flows={data.bilateralFlows}
          showRiskLayer={true}
        />
      </Suspense>
    </WorldMapLayout>
  );
};

export const WorldMap = () => {
  return (
    <ErrorBoundary>
      <VizStoreProvider>
        <WorldMapContent />
      </VizStoreProvider>
    </ErrorBoundary>
  );
};
