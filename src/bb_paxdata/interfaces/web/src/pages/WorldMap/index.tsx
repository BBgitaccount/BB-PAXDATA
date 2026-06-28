// src/bb_paxdata/interfaces/web/src/pages/WorldMap/index.tsx

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Globe, RefreshCw, Zap } from 'lucide-react';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useVizStore } from '../../store/vizStore';
import { sentimentToColor } from '../../utils/visualizationHelpers';
import { WorldMapLayout } from './WorldMapLayout';
import { CountryDrawer } from './components/CountryDrawer';
import { KPIRow } from './components/KPIRow';
import { MapLegend } from './components/MapLegend';
import { SidePanelContent } from './components/SidePanelContent';
import { VizCommandBar } from './components/VizCommandBar';
import { VizStoreProvider } from './components/VizStoreProvider';

// Lazy load heavy components for code splitting
const ChoroplethMap = lazy(() =>
  import('./components/ChoroplethMap').then((m) => ({ default: m.ChoroplethMap })),
);
const NetworkGraph = lazy(() =>
  import('./components/NetworkGraph').then((m) => ({ default: m.NetworkGraph })),
);
const ChordDiagram = lazy(() =>
  import('./components/ChordDiagram').then((m) => ({ default: m.ChordDiagram })),
);
const SankeyFlowDiagram = lazy(() =>
  import('./components/SankeyFlowDiagram').then((m) => ({ default: m.SankeyFlowDiagram })),
);
const SessionTimelinePanel = lazy(() =>
  import('./components/SessionTimelinePanel').then((m) => ({ default: m.SessionTimelinePanel })),
);
const SentimentHeatmap = lazy(() =>
  import('./components/SentimentHeatmap').then((m) => ({ default: m.SentimentHeatmap })),
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
  const [showCountryDrawer, setShowCountryDrawer] = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  // Optimized Zustand selectors - only subscribe to specific fields
  const activeTab = useVizStore((state) => state.activeTab);
  const filters = useVizStore((state) => state.filters);
  const data = useVizStore((state) => state.data);
  const setHighlightedCountry = useVizStore((state) => state.setHighlightedCountry);
  const setSelectedCountryStore = useVizStore((state) => state.setSelectedCountry);
  const fetchAllData = useVizStore((state) => state.fetchAllData);

  // Sync local selected country with vizStore
  const selectedCountry = filters.selectedCountry;
  const highlightedCountry = filters.highlightedCountry;

  // Fetch data on mount
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

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

  // Transform vizStore data to NetworkGraph format
  const networkGraphNodes = useMemo(() => {
    return data.countryNodes.map((n) => ({
      country_code: n.isoAlpha3 || '',
      country_name: n.country,
      latitude: 0,
      longitude: 0,
      total_mentions: n.totalInteractions,
      avg_sentiment: n.avgSentiment,
    }));
  }, [data.countryNodes]);

  const networkGraphConnections = useMemo(() => {
    return data.bilateralFlows.map((f) => ({
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
  }, [data.bilateralFlows]);

  // Show country drawer when country is selected
  useEffect(() => {
    if (selectedCountry) {
      setShowCountryDrawer(true);
    }
  }, [selectedCountry]);

  return (
    <WorldMapLayout
      header={
        <div className="px-4 py-3 flex items-center justify-between">
          <div>
            <h1
              className="text-2xl font-bold tracking-tight flex items-center gap-3"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
            >
              <Globe className="w-6 h-6" style={{ color: 'var(--signal-info)' }} />
              Dünya Haritası
            </h1>
            <p
              className="text-sm mt-1"
              style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
            >
              COĞRAFİ GÖRSELLEŞTİRME // DİPLOMATİK ANALİZ
            </p>
          </div>
          <button
            onClick={() => fetchAllData()}
            className="flex items-center gap-2 px-3 py-2 text-sm transition-colors"
            style={{
              backgroundColor: 'var(--geoint-base)',
              border: 'var(--border-subtle)',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-label)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--geoint-base)';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <RefreshCw className="w-4 h-4" />
            Yenile
          </button>
        </div>
      }
      kpiRow={<KPIRow />}
      tabBar={<VizCommandBar mapContainerRef={mapContainerRef} />}
      sidePanelContent={<SidePanelContent />}
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

      {/* Map Legend - only show on choropleth tab */}
      {activeTab === 'choropleth' && <MapLegend />}

      {/* Tab Content with Suspense for lazy loading */}
      <Suspense fallback={<SkeletonLoader />}>
        {activeTab === 'choropleth' ? (
          <ChoroplethMap
            nodes={nodes}
            connections={connections}
            setSelectedCountry={setSelectedCountryStore}
            highlightedCountry={highlightedCountry}
            setHighlightedCountry={setHighlightedCountry}
            selectedConnection={selectedConnection}
            setSelectedConnection={setSelectedConnection}
            mapContainerRef={mapContainerRef}
            flows={data.bilateralFlows}
            showRiskLayer={true}
          />
        ) : activeTab === 'network' ? (
          <NetworkGraph
            nodes={networkGraphNodes}
            connections={networkGraphConnections}
            selectedCountry={selectedCountry}
            setSelectedCountry={setSelectedCountryStore}
          />
        ) : activeTab === 'chord' ? (
          <ChordDiagram />
        ) : activeTab === 'sankey' ? (
          <SankeyFlowDiagram />
        ) : activeTab === 'heatmap' ? (
          <SentimentHeatmap />
        ) : (
          <SessionTimelinePanel />
        )}
      </Suspense>

      {/* Country Drawer */}
      {showCountryDrawer && selectedCountry && (
        <CountryDrawer
          country={selectedCountry}
          onClose={() => {
            setShowCountryDrawer(false);
            setSelectedCountryStore(null);
          }}
          bilateralFlows={data.bilateralFlows}
          countryNodes={data.countryNodes}
          sessionTimeline={data.sessionTimeline}
        />
      )}
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
