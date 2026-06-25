import { useEffect, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import { BilateralNetworkGraph } from '@/components/BilateralNetworkGraph';
import { useToast } from '@/hooks/useToast';
import { useUIStore } from '@/store/uiStore';
import { useTranslation } from '@/hooks/useTranslation';
import type { BilateralSentimentData, PanelTimelineEntry } from '@/types';
import { Globe, Filter, Download, RefreshCw, Info, Layers, ArrowRightLeft } from 'lucide-react';

export const BilateralRelations = () => {
  const toast = useToast();
  const [selectedPanel, setSelectedPanel] = useState<PanelTimelineEntry | null>(null);
  const theme = useUIStore((s) => s.theme);
  const { t } = useTranslation();

  // Main bilateral data query
  const dashboardQuery = useQuery({
    queryKey: ['bilateral-overview'],
    queryFn: () => apiClient.get<BilateralSentimentData[]>('/api/v1/dashboard/bilateral'),
  });

  // Timeline query for time slider
  const timelineQuery = useQuery({
    queryKey: ['bilateral-timeline'],
    queryFn: () => apiClient.get<PanelTimelineEntry[]>('/api/v1/dashboard/bilateral/timeline'),
    staleTime: 1000 * 60 * 5,
  });

  // Panel-specific bilateral data
  const panelBilateralQuery = useQuery({
    queryKey: ['bilateral-panel', selectedPanel?.file_id],
    queryFn: () =>
      selectedPanel
        ? apiClient.get<BilateralSentimentData[]>(
            `/api/v1/dashboard/bilateral?file_id=${selectedPanel.file_id}`,
          )
        : Promise.resolve(null),
    enabled: !!selectedPanel,
    staleTime: 1000 * 30,
  });

  const handleTimelineStep = useCallback((entry: PanelTimelineEntry | null) => {
    setSelectedPanel(entry);
  }, []);

  // Active bilateral data
  const activeBilateral: BilateralSentimentData[] =
    selectedPanel && panelBilateralQuery.data
      ? panelBilateralQuery.data
      : (dashboardQuery.data ?? []);

  useEffect(() => {
    if (dashboardQuery.isError) {
      toast.error('İkili ilişkiler verileri yüklenemedi.');
    }
  }, [dashboardQuery.isError, toast]);

  if (dashboardQuery.isPending) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-8 h-8 text-carbon-400 animate-spin" />
          <span className="text-sm text-carbon-400">Veriler yükleniyor...</span>
        </div>
      </div>
    );
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <div className="border border-carbon-550 bg-carbon-900 p-6 text-sm text-carbon-300">
        <p className="font-semibold text-carbon-50">İkili ilişkiler verileri alınamadı.</p>
        <p className="mt-2 text-carbon-400">API bağlantısını kontrol edip yeniden deneyin.</p>
        <button
          type="button"
          onClick={() => dashboardQuery.refetch()}
          className="mt-4 btn-primary px-4 py-2 text-xs"
        >
          Tekrar Dene
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50 flex items-center gap-3">
            <Globe className="w-5 h-5 text-indigo-400" />
            İkili İlişkiler Ağı
          </h1>
          <p className="text-sm text-carbon-400 mt-1">
            Ülkeler arası diplomatik ilişkilerin interaktif ağ görselleştirmesi
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => dashboardQuery.refetch()}
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
          <h3 className="text-sm font-semibold text-carbon-50 mb-1">
            İnteraktif Ağ Görselleştirmesi
          </h3>
          <p className="text-xs text-carbon-400 leading-relaxed">
            Bu görselleştirme, ülkeler arası ikili ilişkileri force-directed ağ grafiği olarak
            gösterir. Düğümler ülkeleri, kenarlar ilişkileri temsil eder. Kenar kalınlığı etkileşim
            sayısını, renk ise affinity skorunu gösterir. Zaman çubuğu ile farklı paneller arası
            geçiş yapabilirsiniz.
          </p>
        </div>
      </div>

      {/* Main Visualization */}
      <div className="bg-carbon-900 border border-hair border-carbon-550 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-carbon-550 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-carbon-300">
              <Layers className="w-4 h-4" />
              <span>Ağ Görünümü</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-carbon-400">
              <span className="px-2 py-1 bg-carbon-800 rounded">
                {activeBilateral.length} ilişki
              </span>
              <span className="px-2 py-1 bg-carbon-800 rounded">
                {
                  Array.from(
                    new Set(activeBilateral.flatMap((d) => [d.from_country, d.to_country])),
                  ).length
                }{' '}
                ülke
              </span>
            </div>
          </div>
        </div>

        {activeBilateral && activeBilateral.length > 0 ? (
          <BilateralNetworkGraph
            data={activeBilateral}
            timeline={timelineQuery.data ?? []}
            onTimelineStep={handleTimelineStep}
            playIntervalMs={3000}
          />
        ) : (
          <div className="h-96 flex flex-col items-center justify-center text-carbon-450 border border-dashed border-carbon-550/40">
            <Globe className="w-12 h-12 mb-3 text-carbon-500 opacity-60" />
            <span className="text-sm">İkili ilişkiler veri seti bulunmamaktadır.</span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="bg-carbon-900 border border-hair border-carbon-550 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-carbon-50 mb-3 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4" />
          Görselleştirme Rehberi
        </h3>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <h4 className="text-xs font-medium text-carbon-300 mb-2">Kenar Renkleri (Affinity)</h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-red-700 rounded" />
                <span className="text-xs text-carbon-400">Güçlü Negatif (&lt; -0.7)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-red-400 rounded" />
                <span className="text-xs text-carbon-400">Negatif (-0.4 to -0.7)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-gray-500 rounded" />
                <span className="text-xs text-carbon-400">Nötr (-0.15 to +0.15)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-green-400 rounded" />
                <span className="text-xs text-carbon-400">Pozitif (+0.15 to +0.4)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-1 bg-green-700 rounded" />
                <span className="text-xs text-carbon-400">Güçlü Pozitif (&gt; +0.7)</span>
              </div>
            </div>
          </div>
          <div>
            <h4 className="text-xs font-medium text-carbon-300 mb-2">Kenar Kalınlığı</h4>
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
              <li>• Düğümleri sürükleyip bırakabilirsiniz</li>
              <li>• Tıklayarak detayları görebilirsiniz</li>
              <li>• Scroll ile yakınlaştırabilirsiniz</li>
              <li>• Zaman çubuğu ile panel geçişi</li>
              <li>• Otomatik oynatma modu</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
