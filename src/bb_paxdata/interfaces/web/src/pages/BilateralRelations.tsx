import { useQuery } from '@tanstack/react-query';
import * as d3 from 'd3';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowRightLeft,
  GitCommit,
  Globe,
  Layers,
  RefreshCw,
  ShieldCheck,
  ZoomIn,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import type { BilateralSentimentData, PanelTimelineEntry } from '@/types';

// Helper to determine alliance
const isAlly = (r: BilateralSentimentData) =>
  r.relationship_type === 'ALLY' || (r.affinity_score && r.affinity_score > 0.5);
const isRival = (r: BilateralSentimentData) =>
  r.relationship_type === 'RIVAL' || (r.affinity_score && r.affinity_score < -0.5);

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
        .attr('stroke', '#1e293b')
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
            if (d.id === selectedCountry) return '#1e293b'; // Active focus
            return '#0b0f19'; // Carbon dark slate
          })
          .attr('stroke', '#1e293b')
          .attr('stroke-width', 0.7)
          .style('cursor', 'pointer')
          .style('transition', 'fill 0.2s, stroke 0.2s')
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .on('mouseover', function (_event, d: any) {
            if (d.id !== selectedCountry) {
              d3.select(this).attr('fill', '#161b26');
            }
          })
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          .on('mouseout', function (_event, d: any) {
            if (d.id !== selectedCountry) {
              d3.select(this).attr('fill', '#0b0f19');
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
          .attr('fill', isSelected ? '#10b981' : '#3b82f6')
          .attr('stroke', '#020617')
          .attr('stroke-width', 1.5);

        nodeGroup
          .append('text')
          .attr('x', x + 6)
          .attr('y', y + 3)
          .text(id)
          .attr('fill', '#64748b')
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

        let strokeColor = '#334155';
        let opacity = 0.25;
        let strokeWidth = 1.2;

        if (isAlly(r)) {
          strokeColor = '#10b981'; // Emerald
          opacity = 0.8;
        } else if (isRival(r)) {
          strokeColor = '#ef4444'; // Red
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
  const [viewMode, setViewMode] = useState<ViewMode>('globe');
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const [selectedPanel, setSelectedPanel] = useState<PanelTimelineEntry | null>(null);

  const dashboardQuery = useQuery({
    queryKey: ['bilateral-overview'],
    queryFn: () => apiClient.get<BilateralSentimentData[]>('/api/v1/dashboard/bilateral'),
  });

  const timelineQuery = useQuery({
    queryKey: ['bilateral-timeline'],
    queryFn: () => apiClient.get<PanelTimelineEntry[]>('/api/v1/dashboard/bilateral/timeline'),
    staleTime: 1000 * 60 * 5,
  });

  const mapQuery = useQuery({
    queryKey: ['world-geojson'],
    queryFn: () =>
      d3.json<d3.ExtendedFeatureCollection>(
        'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson',
      ),
    staleTime: Infinity,
  });

  const activeData = useMemo(() => dashboardQuery.data || [], [dashboardQuery.data]);

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

  const stats = useMemo(() => {
    const avgAffinity = d3.mean(activeData, (d) => d.affinity_score || 0) || 0;
    const totalInteractions = d3.sum(activeData, (d) => d.interaction_count || 0);
    const allyCount = activeData.filter(isAlly).length;
    const rivalCount = activeData.filter(isRival).length;
    return {
      avgAffinity,
      totalInteractions,
      allyCount,
      rivalCount,
    };
  }, [activeData]);

  const handleCountrySelect = useCallback((id: string) => {
    setSelectedCountry((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-carbon-50 flex items-center gap-3">
            <Globe className="w-6 h-6 text-carbon-200" />
            Diplomatik İstihbarat Merkezi
          </h1>
          <p className="text-sm text-carbon-400 mt-2 max-w-3xl">
            Küresel müttefiklik ve çatışma ağlarının anlık analiz haritası. Veriler doğrudan
            BilateralSentiment veritabanından çekilmektedir.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => dashboardQuery.refetch()}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-carbon-800 border border-carbon-550 text-carbon-300 hover:text-carbon-100 hover:bg-carbon-700 transition-colors rounded-none"
          >
            <RefreshCw className="w-4 h-4" /> Yenile
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'Müttefik Ülke İlişkileri',
            value: stats.allyCount,
            color: 'text-green-400',
          },
          {
            label: 'Toplam Etkileşim Hacmi',
            value: stats.totalInteractions.toLocaleString(),
            color: 'text-sky-400',
          },
          {
            label: 'Ortalama Yakınlık (Affinity)',
            value: stats.avgAffinity.toFixed(2),
            color: stats.avgAffinity > 0 ? 'text-green-400' : 'text-red-400',
          },
          {
            label: 'Risk ve Çatışma Noktaları',
            value: stats.rivalCount,
            color: 'text-red-400',
          },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="group relative bg-carbon-900 border border-carbon-700 hover:border-carbon-500 p-5 rounded-none transition-all overflow-hidden"
          >
            <div className="relative z-10 flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wider text-carbon-400 font-medium">
                {stat.label}
              </span>
              <span className={`text-3xl font-mono font-bold tracking-tight ${stat.color}`}>
                {stat.value}
              </span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* View Mode Selector */}
      <div className="flex flex-wrap gap-2 border-b border-carbon-700 pb-3">
        {[
          { id: 'globe' as ViewMode, label: '2D Dünya Haritası', icon: Globe },
          {
            id: 'network' as ViewMode,
            label: 'Ağ Bağlantıları',
            icon: GitCommit,
          },
          {
            id: 'chord' as ViewMode,
            label: 'Korelasyon Matrisi',
            icon: ArrowRightLeft,
          },
          { id: 'heatmap' as ViewMode, label: 'Zaman İzlemi', icon: Activity },
        ].map((mode) => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-medium transition-all rounded-none border ${
              viewMode === mode.id
                ? 'bg-carbon-200/10 border-carbon-400 text-carbon-100'
                : 'bg-carbon-800 border-carbon-700 text-carbon-400 hover:text-carbon-200'
            }`}
          >
            <mode.icon className="w-3.5 h-3.5" /> {mode.label}
          </button>
        ))}
      </div>

      {/* Main Content Grid (MAP-CENTRIC LAYOUT) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 relative">
        {(dashboardQuery.isLoading || timelineQuery.isLoading || mapQuery.isLoading) && (
          <div className="absolute inset-0 z-50 bg-carbon-950/50 flex items-center justify-center rounded-none border border-carbon-800/50">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 rounded-full border-2 border-carbon-500/30 border-t-carbon-200 animate-spin" />
              <div className="text-sm font-medium text-carbon-300">
                İstihbarat verileri yükleniyor...
              </div>
            </div>
          </div>
        )}

        {/* 2D Map takes up 2/3 columns and has h-[680px] to be prominent and map-centric */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            <motion.div
              key={viewMode}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.3 }}
              className="bg-carbon-950 rounded-none overflow-hidden border border-carbon-700 h-[680px]"
            >
              {viewMode === 'globe' && (
                <Immersive2DMapView
                  data={activeData}
                  mapData={mapQuery.data}
                  onSelect={handleCountrySelect}
                  selectedCountry={selectedCountry}
                  countriesMetadata={countriesMetadata}
                />
              )}
              {viewMode !== 'globe' && (
                <div className="flex items-center justify-center h-full w-full text-carbon-400 bg-carbon-950">
                  <div className="text-center">
                    <Activity className="w-16 h-16 text-carbon-600 mx-auto mb-4" />
                    <h2 className="text-xl font-bold text-carbon-300">Gelişmiş Görünümler</h2>
                    <p className="mt-2 text-sm text-carbon-400">
                      Bu görünüm harita odaklı yeni tasarıma entegre edilmektedir.
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Side Panels - Stacked nicely on the right */}
        <div className="space-y-6 flex flex-col justify-between">
          <div className="space-y-6">
            {selectedCountry && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-carbon-900 border border-carbon-700 p-5 rounded-none"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-sm font-semibold text-carbon-50 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-green-400" />
                    {countriesMetadata.get(selectedCountry)?.name || selectedCountry} Analiz Detayı
                  </h3>
                  <button
                    onClick={() => setSelectedCountry(null)}
                    className="text-carbon-400 hover:text-carbon-100"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="text-2xs text-carbon-400 uppercase tracking-wider font-semibold border-b border-carbon-700 pb-1 mb-2">
                      Müttefik Ülkeler
                    </div>
                    <div className="space-y-1">
                      {activeData
                        .filter(
                          (r) =>
                            (r.from_country === selectedCountry ||
                              r.to_country === selectedCountry) &&
                            isAlly(r),
                        )
                        .sort((a, b) => (b.affinity_score || 0) - (a.affinity_score || 0))
                        .slice(0, 4)
                        .map((r, i) => {
                          const other =
                            r.from_country === selectedCountry ? r.to_country : r.from_country;
                          const c = countriesMetadata.get(other);
                          return (
                            <div
                              key={i}
                              className="flex justify-between items-center text-xs bg-carbon-950 px-3 py-2 rounded-none border border-carbon-800"
                            >
                              <span className="text-carbon-300 font-medium">
                                {c?.name || other}
                              </span>
                              <span className="text-green-400 font-mono">
                                +{r.affinity_score?.toFixed(2)}
                              </span>
                            </div>
                          );
                        })}
                      {activeData.filter(
                        (r) =>
                          (r.from_country === selectedCountry ||
                            r.to_country === selectedCountry) &&
                          isAlly(r),
                      ).length === 0 && (
                        <div className="text-2xs text-carbon-500 italic">Müttefik bulunamadı.</div>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="text-2xs text-carbon-400 uppercase tracking-wider font-semibold border-b border-carbon-700 pb-1 mb-2">
                      Çatışma / Risk Noktaları
                    </div>
                    <div className="space-y-1">
                      {activeData
                        .filter(
                          (r) =>
                            (r.from_country === selectedCountry ||
                              r.to_country === selectedCountry) &&
                            isRival(r),
                        )
                        .sort((a, b) => (a.affinity_score || 0) - (b.affinity_score || 0))
                        .slice(0, 4)
                        .map((r, i) => {
                          const other =
                            r.from_country === selectedCountry ? r.to_country : r.from_country;
                          const c = countriesMetadata.get(other);
                          return (
                            <div
                              key={i}
                              className="flex justify-between items-center text-xs bg-carbon-950 px-3 py-2 rounded-none border border-red-900/20"
                            >
                              <span className="text-carbon-300 font-medium">
                                {c?.name || other}
                              </span>
                              <span className="text-red-400 font-mono">
                                {r.affinity_score?.toFixed(2)}
                              </span>
                            </div>
                          );
                        })}
                      {activeData.filter(
                        (r) =>
                          (r.from_country === selectedCountry ||
                            r.to_country === selectedCountry) &&
                          isRival(r),
                      ).length === 0 && (
                        <div className="text-2xs text-carbon-500 italic">
                          Riskli ilişki bulunamadı.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            <div className="bg-carbon-900 border border-carbon-700 p-5 rounded-none h-[350px] flex flex-col">
              <h3 className="text-sm font-semibold text-carbon-50 mb-4 flex items-center gap-2">
                <Layers className="w-4 h-4 text-carbon-200" /> Analiz Edilen Oturumlar
              </h3>
              <div className="space-y-2 overflow-y-auto pr-2 custom-scrollbar flex-1">
                {timelineQuery.data?.map((panel) => (
                  <button
                    key={panel.file_id}
                    onClick={() => setSelectedPanel(panel)}
                    className={`w-full text-left px-4 py-3 text-sm rounded-none border transition-all duration-200 ${
                      selectedPanel?.file_id === panel.file_id
                        ? 'bg-carbon-200/10 border-carbon-400 text-carbon-100'
                        : 'bg-carbon-950 border-carbon-800 text-carbon-400 hover:border-carbon-600 hover:bg-carbon-800'
                    }`}
                  >
                    <div className="font-medium truncate">{panel.title}</div>
                    <div className="flex items-center justify-between text-2xs text-carbon-500 mt-2">
                      <span className="font-mono bg-carbon-900 px-1.5 py-0.5 rounded-none border border-carbon-800">
                        {panel.date_str}
                      </span>
                      <span>{panel.speaker_count ?? '?'} konuşmacı</span>
                    </div>
                  </button>
                ))}
                {!timelineQuery.isLoading && !timelineQuery.data?.length && (
                  <div className="text-center py-6 text-carbon-500 text-xs">
                    Zaman çizelgesi verisi bulunamadı.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
