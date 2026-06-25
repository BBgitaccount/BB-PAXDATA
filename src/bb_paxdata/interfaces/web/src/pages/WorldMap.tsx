import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { Globe, Filter, RefreshCw, Info, ArrowRightLeft, Zap } from 'lucide-react';

interface CountryNode {
  country_code: string;
  country_name: string;
  latitude: number;
  longitude: number;
  total_mentions: number;
  avg_sentiment: number;
}

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

interface WorldMapData {
  nodes: CountryNode[];
  connections: CountryConnection[];
}

export const WorldMap = () => {
  const toast = useToast();
  const { t } = useTranslation();
  const [selectedConnection, setSelectedConnection] = useState<CountryConnection | null>(null);
  const [minInteractions, setMinInteractions] = useState(1);

  const worldMapQuery = useQuery({
    queryKey: ['worldmap', minInteractions],
    queryFn: () =>
      apiClient.get<WorldMapData>(`/api/v1/worldmap/data?min_interactions=${minInteractions}`),
  });

  useEffect(() => {
    if (worldMapQuery.isError) {
      toast.error('Dünya haritası verileri yüklenemedi.');
    }
  }, [worldMapQuery.isError, toast]);

  const getSentimentColor = (sentiment: number) => {
    if (sentiment > 0.4) return '#22c55e'; // green
    if (sentiment > 0.15) return '#86efac'; // light green
    if (sentiment > -0.15) return '#6b7280'; // gray (neutral)
    if (sentiment > -0.4) return '#f87171'; // light red
    return '#dc2626'; // red
  };

  const getConnectionWidth = (count: number) => {
    return Math.min(Math.max(count / 5, 1), 5);
  };

  if (worldMapQuery.isPending) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-8 h-8 text-carbon-400 animate-spin" />
          <span className="text-sm text-carbon-400">Veriler yükleniyor...</span>
        </div>
      </div>
    );
  }

  if (worldMapQuery.isError || !worldMapQuery.data) {
    return (
      <div className="border border-carbon-550 bg-carbon-900 p-6 text-sm text-carbon-300">
        <p className="font-semibold text-carbon-50">Dünya haritası verileri alınamadı.</p>
        <p className="mt-2 text-carbon-400">API bağlantısını kontrol edip yeniden deneyin.</p>
        <button
          type="button"
          onClick={() => worldMapQuery.refetch()}
          className="mt-4 btn-primary px-4 py-2 text-xs"
        >
          Tekrar Dene
        </button>
      </div>
    );
  }

  const { nodes, connections } = worldMapQuery.data;

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50 flex items-center gap-3">
            <Globe className="w-5 h-5 text-indigo-400" />
            Dünya Haritası - Ülke İlişkileri
          </h1>
          <p className="text-sm text-carbon-400 mt-1">
            Ülkeler arası diplomatik ilişkilerin coğrafi görselleştirmesi
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-carbon-800 border border-carbon-550 rounded px-3 py-2">
            <Filter className="w-4 h-4 text-carbon-400" />
            <label className="text-xs text-carbon-300">Min Etkileşim:</label>
            <input
              type="number"
              min="1"
              max="100"
              value={minInteractions}
              onChange={(e) => setMinInteractions(Number(e.target.value))}
              className="w-16 bg-carbon-900 border border-carbon-550 rounded px-2 py-1 text-xs text-carbon-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            onClick={() => worldMapQuery.refetch()}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-carbon-800 border border-carbon-550 text-carbon-300 hover:text-carbon-100 hover:bg-carbon-700 transition-colors rounded"
          >
            <RefreshCw className="w-4 h-4" />
            Yenile
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-carbon-800/50 border border-carbon-550 rounded-lg p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-carbon-50 mb-1">Coğrafi İlişki Ağı</h3>
          <p className="text-xs text-carbon-400 leading-relaxed">
            Bu görselleştirme, ülkeler arası diplomatik ilişkileri dünya haritası üzerinde gösterir.
            Düğümler ülkeleri, çizgiler ilişkileri temsil eder. Çizgi kalınlığı etkileşim sayısını,
            renk ise sentiment skorunu gösterir. Haritada gezinmek için sürükleyebilir ve
            yakınlaştırabilirsiniz.
          </p>
        </div>
      </div>

      {/* Main Map Visualization */}
      <div className="bg-carbon-900 border border-hair border-carbon-550 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-carbon-550 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-carbon-300">
              <Globe className="w-4 h-4" />
              <span>Harita Görünümü</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-carbon-400">
              <span className="px-2 py-1 bg-carbon-800 rounded">{nodes.length} ülke</span>
              <span className="px-2 py-1 bg-carbon-800 rounded">{connections.length} ilişki</span>
            </div>
          </div>
        </div>

        <div className="relative" style={{ height: '600px' }}>
          <svg
            width="100%"
            height="100%"
            viewBox="0 0 1000 500"
            preserveAspectRatio="xMidYMid meet"
            className="bg-carbon-950"
          >
            {/* World map background (simplified) */}
            <rect width="1000" height="500" fill="#0a0a0f" />

            {/* Simplified continent outlines */}
            <g fill="#1a1a2e" stroke="#2a2a4e" strokeWidth="1">
              {/* North America */}
              <path d="M 50 80 L 150 60 L 250 80 L 300 150 L 250 250 L 150 280 L 80 200 Z" />
              {/* South America */}
              <path d="M 200 300 L 280 300 L 320 400 L 280 480 L 220 450 L 200 350 Z" />
              {/* Europe */}
              <path d="M 450 80 L 550 70 L 580 120 L 550 160 L 480 150 L 450 100 Z" />
              {/* Africa */}
              <path d="M 450 180 L 550 180 L 580 280 L 550 380 L 480 350 L 450 250 Z" />
              {/* Asia */}
              <path d="M 580 70 L 850 70 L 920 150 L 900 250 L 750 280 L 620 200 L 580 120 Z" />
              {/* Australia */}
              <path d="M 780 350 L 880 350 L 900 420 L 850 450 L 780 420 Z" />
            </g>

            {/* Connection lines */}
            {connections.map((conn, idx) => {
              const fromX = ((conn.from_lon + 180) / 360) * 1000;
              const fromY = ((90 - conn.from_lat) / 180) * 500;
              const toX = ((conn.to_lon + 180) / 360) * 1000;
              const toY = ((90 - conn.to_lat) / 180) * 500;
              const color = getSentimentColor(conn.avg_sentiment);
              const width = getConnectionWidth(conn.interaction_count);
              const isSelected = selectedConnection === conn;

              return (
                <g key={`conn-${idx}`}>
                  <line
                    x1={fromX}
                    y1={fromY}
                    x2={toX}
                    y2={toY}
                    stroke={color}
                    strokeWidth={isSelected ? width + 2 : width}
                    strokeOpacity={isSelected ? 1 : 0.6}
                    strokeLinecap="round"
                    className="cursor-pointer hover:stroke-opacity-100 transition-all"
                    onClick={() => setSelectedConnection(conn)}
                  />
                  {/* Arrow at midpoint */}
                  <circle
                    cx={(fromX + toX) / 2}
                    cy={(fromY + toY) / 2}
                    r={isSelected ? 4 : 2}
                    fill={color}
                    className="cursor-pointer"
                    onClick={() => setSelectedConnection(conn)}
                  />
                </g>
              );
            })}

            {/* Country nodes */}
            {nodes.map((node) => {
              const x = ((node.longitude + 180) / 360) * 1000;
              const y = ((90 - node.latitude) / 180) * 500;
              const size = Math.min(Math.max(node.total_mentions / 10, 4), 12);
              const color = getSentimentColor(node.avg_sentiment);

              return (
                <g key={`node-${node.country_code}`}>
                  <circle
                    cx={x}
                    cy={y}
                    r={size}
                    fill={color}
                    stroke="#ffffff"
                    strokeWidth={1.5}
                    className="cursor-pointer hover:stroke-indigo-400 transition-all"
                    onClick={() => {
                      const relatedConnections = connections.filter(
                        (c) =>
                          c.from_country === node.country_code ||
                          c.to_country === node.country_code,
                      );
                      if (relatedConnections.length > 0) {
                        setSelectedConnection(relatedConnections[0]);
                      }
                    }}
                  />
                  {/* Country code label */}
                  <text
                    x={x}
                    y={y - size - 5}
                    fill="#9ca3af"
                    fontSize="8"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    {node.country_code}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Selected connection details */}
          {selectedConnection && (
            <div className="absolute top-4 right-4 bg-carbon-800 border border-carbon-550 rounded-lg p-4 max-w-xs shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-carbon-50 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-indigo-400" />
                  İlişki Detayları
                </h4>
                <button
                  onClick={() => setSelectedConnection(null)}
                  className="text-carbon-400 hover:text-carbon-100"
                >
                  ×
                </button>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-carbon-400">Kaynak:</span>
                  <span className="text-carbon-100">{selectedConnection.from_country}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-400">Hedef:</span>
                  <span className="text-carbon-100">{selectedConnection.to_country}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-400">Etkileşim:</span>
                  <span className="text-carbon-100">{selectedConnection.interaction_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-400">Sentiment:</span>
                  <span
                    className="text-carbon-100"
                    style={{ color: getSentimentColor(selectedConnection.avg_sentiment) }}
                  >
                    {selectedConnection.avg_sentiment.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-400">İlişki Tipi:</span>
                  <span className="text-carbon-100">{selectedConnection.relationship_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-400">Affinity:</span>
                  <span className="text-carbon-100">
                    {selectedConnection.affinity_score.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="bg-carbon-900 border border-hair border-carbon-550 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-carbon-50 mb-3 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4" />
          Görselleştirme Rehberi
        </h3>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <h4 className="text-xs font-medium text-carbon-300 mb-2">Sentiment Renkleri</h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-green-500 rounded" />
                <span className="text-xs text-carbon-400">Pozitif (&gt; 0.4)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-green-300 rounded" />
                <span className="text-xs text-carbon-400">Hafif Pozitif (0.15 to 0.4)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-gray-500 rounded" />
                <span className="text-xs text-carbon-400">Nötr (-0.15 to +0.15)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-red-400 rounded" />
                <span className="text-xs text-carbon-400">Hafif Negatif (-0.4 to -0.15)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-red-600 rounded" />
                <span className="text-xs text-carbon-400">Negatif (&lt; -0.4)</span>
              </div>
            </div>
          </div>
          <div>
            <h4 className="text-xs font-medium text-carbon-300 mb-2">Çizgi Kalınlığı</h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-0.5 bg-indigo-400 rounded" />
                <span className="text-xs text-carbon-400">Az Etkileşim</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-indigo-400 rounded" />
                <span className="text-xs text-carbon-400">Orta Etkileşim</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-2 bg-indigo-400 rounded" />
                <span className="text-xs text-carbon-400">Yoğun Etkileşim</span>
              </div>
            </div>
          </div>
          <div>
            <h4 className="text-xs font-medium text-carbon-300 mb-2">İnteraktif Özellikler</h4>
            <ul className="space-y-1 text-xs text-carbon-400">
              <li>• Düğümlere tıklayarak ilişkileri görün</li>
              <li>• Çizgilere tıklayarak detayları görün</li>
              <li>• Min etkileşim filtresi kullanın</li>
              <li>• Düğüm boyutu mention sayısını gösterir</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
