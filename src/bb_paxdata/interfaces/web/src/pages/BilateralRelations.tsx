import type { BilateralSentimentData } from '@/types';
import { useQuery } from '@tanstack/react-query';
import * as d3 from 'd3';
import { AnimatePresence, motion } from 'framer-motion';
import { Activity, Globe, ZoomIn } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVizStore } from '../store/vizStore';
import type { BilateralFlow } from '../types/visualization';
import { BilateralRelationsLayout } from './BilateralRelations/BilateralRelationsLayout';
import { BilateralCommandBar } from './BilateralRelations/components/BilateralCommandBar';
import { BilateralCountryDrawer } from './BilateralRelations/components/BilateralCountryDrawer';
import { BilateralKPIRow } from './BilateralRelations/components/BilateralKPIRow';
import { BilateralSidePanelContent } from './BilateralRelations/components/BilateralSidePanelContent';

// Helper to determine alliance
const isAlly = (r: BilateralSentimentData) =>
  r.relationship_type === 'ALLY' || (r.affinity_score && r.affinity_score > 0.5);
const isRival = (r: BilateralSentimentData) =>
  r.relationship_type === 'RIVAL' || (r.affinity_score && r.affinity_score < -0.5);

// Transform vizStore BilateralFlow to BilateralSentimentData format
const transformBilateralFlow = (flow: BilateralFlow): BilateralSentimentData => ({
  from_country: flow.fromCountry,
  to_country: flow.toCountry,
  interaction_count: flow.interactionCount,
  avg_sentiment: flow.avgSentiment,
  affinity_score: flow.affinityScore,
  relationship_type: flow.relationshipType,
});

// ─── D3 HOOK ─────────────────────────────────────────────────────
const useD3 = (
  renderFn: (
    svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
    width: number,
    height: number,
  ) => void,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  deps: any[],
) => {
  const ref = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    renderFn(svg, width, height);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ref, containerRef };
};

// ─── IMMERSIVE 2D MAP VIEW ───────────────────────────────────────
const Immersive2DMapView = ({
  data,
  mapData,
  onSelect,
  selectedCountry,
  countriesMetadata,
}: {
  data: BilateralSentimentData[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  mapData: any;
  onSelect: (c: string) => void;
  selectedCountry: string | null;
  countriesMetadata: Map<string, { name: string; center: [number, number] }>;
}) => {
  const { ref, containerRef } = useD3(
    (svg, w, h) => {
      const projection = d3
        .geoMercator()
        .scale(w / 6.2)
        .translate([w / 2, h / 1.5]);
      const path = d3.geoPath().projection(projection);
      const g = svg.append('g');

      // Zoom & Pan
      const zoom = d3
        .zoom()
        .scaleExtent([1, 8])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      svg.call(zoom as any);

      // Graticule (Grid lines)
      const graticule = d3.geoGraticule();
      g.append('path')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .datum(graticule() as any)
        .attr('fill', 'none')
        .attr('stroke', 'var(--border-hair)')
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.4)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .attr('d', path as any);

      // Draw countries
      if (mapData && mapData.features) {
        g.selectAll('.country-path')
          .data(mapData.features)
          .join('path')
          .attr('class', 'country-path')
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .attr('d', path as any)
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .attr('fill', (d: any) => {
            if (d.id === selectedCountry) return 'var(--bg-quaternary)'; // Active focus
            return 'var(--bg-secondary)'; // Carbon deep background
          })
          .attr('stroke', 'var(--border-hair)')
          .attr('stroke-width', 0.7)
          .style('cursor', 'pointer')
          .style('transition', 'fill 0.2s, stroke 0.2s')
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .on('mouseover', function (_event, d: any) {
            if (d.id !== selectedCountry) {
              d3.select(this).attr('fill', 'var(--bg-tertiary)');
            }
          })
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .on('mouseout', function (_event, d: any) {
            if (d.id !== selectedCountry) {
              d3.select(this).attr('fill', 'var(--bg-secondary)');
            }
          })
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .on('click', (_event, d: any) => {
            if (d.id) onSelect(d.id);
          });
      }

      // Draw Capital/Country points only for active countries in relations data
      const activeCountryIds = new Set<string>();
      data.forEach((r) => {
        if (r.from_country) activeCountryIds.add(r.from_country);
        if (r.to_country) activeCountryIds.add(r.to_country);
      });

      activeCountryIds.forEach((id) => {
        const metadata = countriesMetadata.get(id);
        if (!metadata) return;

        const coords = projection(metadata.center);
        if (!coords) return;
        const [x, y] = coords;
        const isSelected = id === selectedCountry;

        const nodeGroup = g
          .append('g')
          .style('cursor', 'pointer')
          .on('click', () => onSelect(id));

        nodeGroup
          .append('circle')
          .attr('cx', x)
          .attr('cy', y)
          .attr('r', isSelected ? 5.5 : 3.5)
          .attr('fill', isSelected ? 'var(--sentiment-ally)' : 'var(--sentiment-partner)')
          .attr('stroke', 'var(--bg-primary)')
          .attr('stroke-width', 1.5);

        nodeGroup
          .append('text')
          .attr('x', x + 6)
          .attr('y', y + 3)
          .text(id)
          .attr('fill', 'var(--text-secondary)')
          .attr('font-size', '8px')
          .attr('font-family', 'monospace')
          .attr('pointer-events', 'none');
      });

      // Draw Relations as curved arcs
      data.forEach((r) => {
        const fromMeta = countriesMetadata.get(r.from_country);
        const toMeta = countriesMetadata.get(r.to_country);
        if (!fromMeta || !toMeta) return;

        const f = projection(fromMeta.center);
        const t = projection(toMeta.center);
        if (!f || !t) return;

        const dx = t[0] - f[0];
        const dy = t[1] - f[1];
        const dr = Math.sqrt(dx * dx + dy * dy);

        // Curved arc path
        const arcPath = `M${f[0]},${f[1]}A${dr},${dr} 0 0,1 ${t[0]},${t[1]}`;

        let strokeColor = 'var(--text-tertiary)';
        let opacity = 0.25;
        let strokeWidth = 1.2;

        if (isAlly(r)) {
          strokeColor = 'var(--sentiment-ally)'; // Emerald
          opacity = 0.8;
        } else if (isRival(r)) {
          strokeColor = 'var(--sentiment-adversary)'; // Red
          opacity = 0.8;
        }

        const isConnectedToSelected =
          selectedCountry &&
          (r.from_country === selectedCountry || r.to_country === selectedCountry);
        if (selectedCountry) {
          if (isConnectedToSelected) {
            opacity = 0.95;
            strokeWidth = 2.2;
          } else {
            opacity = 0.04; // Fade others
          }
        }

        g.append('path')
          .attr('d', arcPath)
          .attr('fill', 'none')
          .attr('stroke', strokeColor)
          .attr('stroke-dasharray', isRival(r) ? '3,3' : 'none')
          .attr('stroke-width', strokeWidth)
          .attr('opacity', opacity)
          .attr('stroke-linecap', 'round');
      });
    },
    [data, mapData, onSelect, selectedCountry, countriesMetadata],
  );

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative bg-carbon-950 rounded-none border border-carbon-700 overflow-hidden"
    >
      <svg ref={ref} className="w-full h-full cursor-grab active:cursor-grabbing" />
      <div className="absolute bottom-3 right-3 flex items-center gap-2 bg-carbon-900 border border-carbon-800 p-2 text-2xs text-carbon-400 rounded-none">
        <ZoomIn className="w-3.5 h-3.5 text-carbon-200" /> Sol Tık + Sürükle ile haritada
        gezinebilir, tekerlek ile zoom yapabilirsiniz.
      </div>
    </div>
  );
};

// ─── MAIN COMPONENT ────────────────────────────────────────────────
type ViewMode = 'globe' | 'network' | 'chord' | 'heatmap';

export const BilateralRelations = () => {
  const [viewMode] = useState<ViewMode>('globe');
  const mapContainerRef = useRef<HTMLDivElement>(null);

  // Use vizStore for data fetching (same as WorldMap)
  const {
    data,
    loading,
    fetchAllData,
    setSelectedCountry: setSelectedCountryStore,
    setHighlightedCountry,
  } = useVizStore();

  const { countryNodes, bilateralFlows, sessionTimeline } = data;

  // Fetch data on mount
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Handle close country drawer event
  useEffect(() => {
    const handleCloseDrawer = () => {
      setSelectedCountryStore(null);
    };
    window.addEventListener('close-country-drawer', handleCloseDrawer);
    return () => window.removeEventListener('close-country-drawer', handleCloseDrawer);
  }, [setSelectedCountryStore]);

  // Sync local selected country with vizStore
  const selectedCountryStore = useVizStore((state) => state.filters.selectedCountry);

  const mapQuery = useQuery({
    queryKey: ['world-geojson'],
    queryFn: () =>
      d3.json<d3.ExtendedFeatureCollection>(
        'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson',
      ),
    staleTime: Infinity,
  });

  // Transform vizStore data to BilateralSentimentData format
  const activeData = useMemo(() => {
    return bilateralFlows.map(transformBilateralFlow);
  }, [bilateralFlows]);

  // Dynamically map GeoJSON country data to construct metadata table (no hardcoded COUNTRIES list!)
  const countriesMetadata = useMemo(() => {
    const map = new Map<string, { name: string; center: [number, number] }>();
    if (mapQuery.data && mapQuery.data.features) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mapQuery.data.features.forEach((d: any) => {
        if (d.id) {
          map.set(d.id, {
            name: d.properties?.name || d.id,
            center: d3.geoCentroid(d),
          });
        }
      });
    }
    return map;
  }, [mapQuery.data]);

  const handleCountrySelect = useCallback(
    (id: string) => {
      setSelectedCountryStore(id);
      setHighlightedCountry(id);
    },
    [setSelectedCountryStore, setHighlightedCountry],
  );

  return (
    <BilateralRelationsLayout
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
              İkili İlişkiler Haritası
            </span>
          </div>
        </div>
      }
      kpiRow={<BilateralKPIRow />}
      tabBar={<BilateralCommandBar mapContainerRef={mapContainerRef} />}
      sidePanelContent={<BilateralSidePanelContent />}
      countryDrawer={
        selectedCountryStore && (
          <BilateralCountryDrawer
            country={selectedCountryStore}
            onClose={() => setSelectedCountryStore(null)}
            bilateralFlows={bilateralFlows}
            countryNodes={countryNodes}
            sessionTimeline={sessionTimeline}
          />
        )
      }
    >
      {/* Main Map Content */}
      <div className="h-full w-full relative">
        {(loading.fetchAll || mapQuery.isLoading) && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-[var(--bg-secondary)]/50">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--signal-info)] animate-spin" />
              <div className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                İstihbarat verileri yükleniyor...
              </div>
            </div>
          </div>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={viewMode}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.3 }}
            className="h-full w-full"
          >
            {viewMode === 'globe' && (
              <Immersive2DMapView
                data={activeData}
                mapData={mapQuery.data}
                onSelect={handleCountrySelect}
                selectedCountry={selectedCountryStore}
                countriesMetadata={countriesMetadata}
              />
            )}
            {viewMode !== 'globe' && (
              <div
                className="flex items-center justify-center h-full w-full"
                style={{ color: 'var(--text-tertiary)', backgroundColor: 'var(--bg-secondary)' }}
              >
                <div className="text-center">
                  <Activity
                    className="w-16 h-16 mx-auto mb-4"
                    style={{ color: 'var(--border-subtle)' }}
                  />
                  <h2 className="text-xl font-bold" style={{ color: 'var(--text-secondary)' }}>
                    Gelişmiş Görünümler
                  </h2>
                  <p className="mt-2 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                    Bu görünüm harita odaklı yeni tasarıma entegre edilmektedir.
                  </p>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </BilateralRelationsLayout>
  );
};
