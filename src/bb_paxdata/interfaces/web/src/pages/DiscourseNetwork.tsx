import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import { DiscourseNetworkExplorer } from '@/components/DiscourseNetworkExplorer';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import type { DiscourseNetworkResponse } from '@/types';
import { SlidersHorizontal, Search, RefreshCw, Calendar, Database } from 'lucide-react';

export const DiscourseNetwork = () => {
  const toast = useToast();
  const { t } = useTranslation();
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [minWeight, setMinWeight] = useState<number>(0.2);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Fetch all unique sessions from backend
  const sessionsQuery = useQuery({
    queryKey: ['discourse-sessions'],
    queryFn: () => apiClient.get<string[]>('/api/v1/discourse/sessions'),
    staleTime: 5 * 60 * 1000,
  });

  // Automatically select the latest session once loaded
  useEffect(() => {
    if (sessionsQuery.data && sessionsQuery.data.length > 0 && !selectedSession) {
      // Select the last session in the sorted list (usually the latest)
      setSelectedSession(sessionsQuery.data[sessionsQuery.data.length - 1]);
    }
  }, [sessionsQuery.data, selectedSession]);

  // Fetch network data for the selected session
  const networkQuery = useQuery({
    queryKey: ['discourse-network', selectedSession],
    queryFn: () =>
      apiClient.get<DiscourseNetworkResponse>(
        `/api/v1/discourse?session_id=${selectedSession}&min_weight=0`,
      ),
    enabled: !!selectedSession,
    staleTime: 60 * 1000,
  });

  const handleRefresh = () => {
    void sessionsQuery.refetch();
    if (selectedSession) {
      void networkQuery.refetch();
    }
    toast.info('Veriler tazeleniyor...');
  };

  // Perform search filtering in-memory
  const filteredData = useMemo(() => {
    const data = networkQuery.data;
    if (!data) return { nodes: [], edges: [] };

    if (!searchQuery.trim()) {
      return data;
    }

    const query = searchQuery.toLowerCase().trim();
    const filteredNodes = data.nodes.filter(
      (n) => n.id.toLowerCase().includes(query) || n.label.toLowerCase().includes(query),
    );
    const matchedNodeIds = new Set(filteredNodes.map((n) => n.id));

    // Keep edges where either source or target matches the search query
    // This allows searching for an actor to see all their concepts, or searching for a concept to see all its actors
    const filteredEdges = data.edges.filter(
      (e) => matchedNodeIds.has(e.source) || matchedNodeIds.has(e.target),
    );

    // Re-resolve nodes that are connected via the matched edges to keep connections visible
    const connectedNodeIds = new Set<string>();
    filteredEdges.forEach((e) => {
      connectedNodeIds.add(e.source);
      connectedNodeIds.add(e.target);
    });

    const finalNodes = data.nodes.filter((n) => connectedNodeIds.has(n.id));

    return {
      nodes: finalNodes,
      edges: filteredEdges,
    };
  }, [networkQuery.data, searchQuery]);

  // Handle error notifications
  useEffect(() => {
    if (sessionsQuery.isError) {
      toast.error('Oturum listesi yüklenemedi.');
    }
    if (networkQuery.isError) {
      toast.error('Söylem ağı verisi yüklenemedi.');
    }
  }, [sessionsQuery.isError, networkQuery.isError, toast]);

  const isPending = sessionsQuery.isPending || networkQuery.isPending;

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('discourse.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('discourse.desc')}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isPending}
          className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-xs border-carbon-600 hover:bg-carbon-800 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isPending ? 'animate-spin' : ''}`} />
          Tazele
        </button>
      </div>

      {/* Control Panel / Filter bar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 border border-hair border-carbon-550 bg-carbon-900 p-5">
        {/* Session Dropdown */}
        <div className="flex flex-col gap-1.5">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <Calendar className="w-3 h-3" />
            Analiz Oturumu (Session ID)
          </label>
          <select
            value={selectedSession}
            onChange={(e) => setSelectedSession(e.target.value)}
            disabled={sessionsQuery.isPending}
            className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs px-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400 disabled:opacity-50"
          >
            {sessionsQuery.isPending && <option>Yükleniyor...</option>}
            {!sessionsQuery.isPending &&
              (!sessionsQuery.data || sessionsQuery.data.length === 0) && (
                <option value="">Oturum kaydı bulunamadı</option>
              )}
            {sessionsQuery.data?.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Min Weight Slider */}
        <div className="flex flex-col gap-1.5 lg:col-span-2">
          <div className="flex justify-between items-center text-3xs uppercase tracking-wider text-carbon-400 font-semibold">
            <span className="flex items-center gap-1.5">
              <SlidersHorizontal className="w-3 h-3" />
              Min. Fischer Eşik Ağırlığı
            </span>
            <span className="font-mono text-carbon-200 text-2xs bg-carbon-850 px-1 py-0.5">
              {minWeight.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-3 h-9">
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={minWeight}
              onChange={(e) => setMinWeight(parseFloat(e.target.value))}
              className="flex-1 accent-carbon-200 bg-carbon-950 h-1 appearance-none cursor-pointer border-none"
            />
            <div className="flex justify-between text-4xs text-carbon-500 font-mono w-8">
              <span>0.0</span>
              <span>1.0</span>
            </div>
          </div>
        </div>

        {/* Text Search */}
        <div className="flex flex-col gap-1.5">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <Search className="w-3 h-3" />
            Aktör / Kavram Arama
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder="Filtrele..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs pl-8 pr-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400 placeholder-carbon-600"
            />
            <Search className="w-3.5 h-3.5 text-carbon-600 absolute left-2.5 top-2.5 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Main visualization container */}
      {selectedSession ? (
        networkQuery.isPending ? (
          <div className="border border-hair border-carbon-550 bg-carbon-900/50 p-20 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-carbon-400 animate-spin" />
            <span className="text-xs text-carbon-350 font-mono">Söylem Ağı yükleniyor...</span>
          </div>
        ) : networkQuery.isError ? (
          <div className="border border-hair border-carbon-550 bg-carbon-900/50 p-20 text-center space-y-4">
            <p className="text-xs text-carbon-300 font-semibold">
              Oturum verileri alınırken bir hata oluştu.
            </p>
            <button
              type="button"
              onClick={() => networkQuery.refetch()}
              className="btn-primary text-2xs px-4 py-2"
            >
              Yeniden Dene
            </button>
          </div>
        ) : (
          <DiscourseNetworkExplorer
            nodes={filteredData.nodes}
            edges={filteredData.edges}
            minWeight={minWeight}
          />
        )
      ) : (
        <div className="border border-hair border-carbon-800 bg-carbon-900/30 p-20 text-center text-xs text-carbon-500 flex flex-col items-center justify-center gap-3">
          <Database className="w-8 h-8 text-carbon-600 animate-[blink-status_2s_ease-in-out_infinite]" />
          <p>Lütfen söylem ağını yüklemek için bir Analiz Oturumu (Session ID) seçin.</p>
        </div>
      )}
    </div>
  );
};
