import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Filter,
  Info,
  RefreshCw,
  Search,
  Sliders,
  User,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { apiClient } from '@/services/apiClient';
import type { AnomalyTimelineItem, PanelTimelineEntry } from '@/types';
import { cn } from '@/utils/helpers';

export const AnomalyTimeline = () => {
  const toast = useToast();
  const { t } = useTranslation();
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [minDiscrepancy, setMinDiscrepancy] = useState<number>(0.0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({});

  // Fetch unique panels/files for dropdown filter
  const panelsQuery = useQuery({
    queryKey: ['bilateral-timeline'],
    queryFn: () => apiClient.get<PanelTimelineEntry[]>('/api/v1/dashboard/bilateral/timeline'),
    staleTime: 1000 * 60 * 5, // 5 dk - panel list changes infrequently
  });

  // Fetch anomalies based on filters
  const anomaliesQuery = useQuery({
    queryKey: ['dashboard-anomalies', selectedFile, selectedCategory, minDiscrepancy],
    queryFn: () => {
      const params = new URLSearchParams();
      if (selectedFile) params.set('file_id', selectedFile);
      if (selectedCategory) params.set('category', selectedCategory);
      if (minDiscrepancy > 0.0) params.set('min_discrepancy', minDiscrepancy.toString());

      return apiClient.get<AnomalyTimelineItem[]>(
        `/api/v1/dashboard/anomalies?${params.toString()}`,
      );
    },
    staleTime: 30 * 1000,
  });

  const toggleExpand = (failId: number) => {
    setExpandedIds((prev) => ({ ...prev, [failId]: !prev[failId] }));
  };

  const handleRefresh = () => {
    void anomaliesQuery.refetch();
    void panelsQuery.refetch();
    toast.info('Zaman çizelgesi tazeleniyor...');
  };

  // Perform client-side keyword filtering
  const filteredAnomalies = useMemo(() => {
    const data = anomaliesQuery.data ?? [];
    if (!searchQuery.trim()) return data;

    const q = searchQuery.toLowerCase().trim();
    return data.filter(
      (item) =>
        (item.original_sentence && item.original_sentence.toLowerCase().includes(q)) ||
        (item.speaker_name && item.speaker_name.toLowerCase().includes(q)) ||
        (item.country && item.country.toLowerCase().includes(q)) ||
        (item.check_type && item.check_type.toLowerCase().includes(q)) ||
        (item.fail_reason && item.fail_reason.toLowerCase().includes(q)),
    );
  }, [anomaliesQuery.data, searchQuery]);

  // Handle errors
  useEffect(() => {
    if (anomaliesQuery.isError) {
      toast.error('Anomali verileri yüklenemedi.');
    }
  }, [anomaliesQuery.isError, toast]);

  const categories = [
    { value: '', label: 'Tüm Kategoriler' },
    { value: 'contradiction', label: 'Çelişki (Contradiction)' },
    { value: 'hedging', label: 'Hedging Volatility' },
    { value: 'risk', label: 'Risk Divergence' },
    { value: 'topic_shift', label: 'Konu Kayması (Topic Shift)' },
    { value: 'politeness', label: 'Politeness Shift' },
    { value: 'sbi', label: 'SBI Inconsistency' },
  ];

  // Helper to format date string nicely
  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return 'Bilinmiyor';
    try {
      const d = new Date(dateStr);
      return d.toLocaleString('tr-TR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  // Category specific CSS classes
  const getCategoryStyles = (category: string | null) => {
    const cat = (category || '').toLowerCase();
    if (cat.includes('contradiction') || cat.includes('çelişki')) {
      return {
        badge: 'bg-red-950/40 text-red-400 border-red-900',
        marker: 'bg-red-500 ring-red-950',
      };
    }
    if (cat.includes('risk') || cat.includes('divergence')) {
      return {
        badge: 'bg-orange-950/40 text-orange-400 border-orange-900',
        marker: 'bg-orange-500 ring-orange-950',
      };
    }
    if (cat.includes('hedging') || cat.includes('volatility')) {
      return {
        badge: 'bg-amber-950/40 text-amber-400 border-amber-900',
        marker: 'bg-amber-500 ring-amber-950',
      };
    }
    return {
      badge: 'bg-carbon-800 text-carbon-300 border-carbon-700',
      marker: 'bg-carbon-400 ring-carbon-900',
    };
  };

  const isPending = anomaliesQuery.isPending || panelsQuery.isPending;

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('anomalies.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('anomalies.desc')}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isPending}
          className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-xs border-carbon-600 hover:bg-carbon-800 disabled:opacity-50"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', isPending && 'animate-spin')} />
          Tazele
        </button>
      </div>

      {/* Filter panel */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 border border-hair border-carbon-550 bg-carbon-900 p-5">
        {/* Category Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" />
            Anomali Kategorisi
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs px-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400"
          >
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {/* Panel/File Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5" />
            Panel (Dosya ID)
          </label>
          <select
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
            disabled={panelsQuery.isPending}
            className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs px-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400 disabled:opacity-50"
          >
            <option value="">Tüm Paneller</option>
            {panelsQuery.data?.map((p) => (
              <option key={p.file_id} value={p.file_id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>

        {/* Discrepancy Score Slider */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center text-3xs uppercase tracking-wider text-carbon-400 font-semibold">
            <span className="flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              Min. Uyumsuzluk (Discrepancy)
            </span>
            <span className="font-mono text-carbon-200 text-2xs bg-carbon-850 px-1 py-0.5">
              {minDiscrepancy.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-3 h-9">
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={minDiscrepancy}
              onChange={(e) => setMinDiscrepancy(parseFloat(e.target.value))}
              className="flex-1 accent-carbon-200 bg-carbon-950 h-1 appearance-none cursor-pointer border-none"
            />
          </div>
        </div>

        {/* Search filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-3xs uppercase tracking-wider text-carbon-400 font-semibold flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5" />
            Detaylı Arama
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder="Konuşmacı, cümle, neden..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-carbon-950 border border-hair border-carbon-700 text-xs pl-8 pr-3 py-2 text-carbon-100 focus:outline-none focus:border-carbon-400 placeholder-carbon-600"
            />
            <Search className="w-3.5 h-3.5 text-carbon-600 absolute left-2.5 top-2.5 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Timeline view */}
      {isPending ? (
        <div className="border border-hair border-carbon-550 bg-carbon-900/50 p-20 flex flex-col items-center justify-center gap-3">
          <RefreshCw className="w-8 h-8 text-carbon-400 animate-spin" />
          <span className="text-xs text-carbon-350 font-mono">Zaman çizelgesi yükleniyor...</span>
        </div>
      ) : filteredAnomalies.length === 0 ? (
        <div className="border border-hair border-carbon-800 bg-carbon-900/30 p-20 text-center text-xs text-carbon-500 flex flex-col items-center justify-center gap-2">
          <AlertTriangle className="w-6 h-6 text-carbon-600" />
          <p className="font-semibold text-carbon-350">
            Seçilen filtrelere uyan anomali kaydı bulunamadı.
          </p>
          <p className="text-carbon-500">
            Kriterleri yumuşatarak veya farklı bir kategori seçerek tekrar deneyin.
          </p>
        </div>
      ) : (
        <div className="relative border-l-2 border-carbon-800 ml-3 md:ml-32 pl-6 md:pl-8 space-y-8 py-4">
          {filteredAnomalies.map((item) => {
            const isExpanded = !!expandedIds[item.fail_id];
            const styles = getCategoryStyles(item.fail_category);

            return (
              <div key={item.fail_id} className="relative group">
                {/* Timeline node marker */}
                <div
                  className={cn(
                    'absolute -left-[33px] md:-left-[41px] top-1.5 w-4 h-4 rounded-full border-2 border-carbon-950 ring-4 transition-transform duration-swift group-hover:scale-125 z-10',
                    styles.marker,
                  )}
                />

                {/* Left floating timestamp on desktop screens */}
                <div className="hidden md:block absolute -left-36 top-1 w-28 text-right pr-2">
                  <span className="text-4xs font-mono text-carbon-400 block leading-tight">
                    {formatDateTime(item.processed_at).split(',')[0]}
                  </span>
                  <span className="text-4xs font-mono text-carbon-500 block mt-0.5">
                    {formatDateTime(item.processed_at).split(',')[1]}
                  </span>
                </div>

                {/* Main Anomaly Card */}
                <div className="border border-hair border-carbon-800 bg-carbon-900/70 p-5 space-y-3 transition-colors hover:border-carbon-600">
                  {/* Card Header */}
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 bg-carbon-800 border border-hair border-carbon-700 flex items-center justify-center text-carbon-300">
                        <User className="w-3.5 h-3.5" />
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-carbon-100">
                          {item.speaker_name || 'Bilinmeyen Konuşmacı'}
                        </span>
                        <span className="text-3xs text-carbon-400 font-medium ml-2">
                          ({item.country || 'Uluslararası'})
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Mobile timestamp fallback */}
                      <span className="md:hidden text-4xs font-mono text-carbon-400 bg-carbon-800/40 px-1.5 py-0.5 flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {formatDateTime(item.processed_at)}
                      </span>

                      <span
                        className={cn(
                          'text-4xs px-2 py-0.5 border font-semibold tracking-wider uppercase',
                          styles.badge,
                        )}
                      >
                        {item.fail_category || 'Genel Anomali'}
                      </span>

                      <span className="text-4xs font-mono text-carbon-400 bg-carbon-850 px-2 py-0.5">
                        Eşik Farkı: {item.discrepancy_score?.toFixed(3) || '0.000'}
                      </span>
                    </div>
                  </div>

                  {/* Sentence content */}
                  <div className="text-sm font-medium text-carbon-150 leading-relaxed border-l-2 border-carbon-600 pl-3 py-1">
                    "{item.original_sentence}"
                  </div>

                  {/* Score breakdown bar */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-carbon-950/40 p-2.5 border border-hair border-carbon-850 text-3xs font-mono">
                    <div>
                      <span className="block text-carbon-500">Denetleme Tipi</span>
                      <span className="text-carbon-300 font-semibold truncate block">
                        {item.check_type}
                      </span>
                    </div>
                    <div>
                      <span className="block text-carbon-500">Hesaplanan Değer</span>
                      <span className="text-carbon-300 font-semibold block">
                        {item.formula_value || 'None'}
                      </span>
                    </div>
                    <div>
                      <span className="block text-carbon-500">AI Değerlendirmesi</span>
                      <span className="text-carbon-300 font-semibold block">
                        {item.ai_value || 'None'}
                      </span>
                    </div>
                    <div>
                      <span className="block text-carbon-500">Dosya/Panel ID</span>
                      <span className="text-carbon-300 font-semibold block truncate">
                        {item.file_id || 'None'}
                      </span>
                    </div>
                  </div>

                  {/* AI Explanation / Reasoning */}
                  {item.fail_reason && (
                    <div className="bg-carbon-950/60 p-3 border-l-2 border-carbon-500 flex gap-2">
                      <Info className="w-3.5 h-3.5 text-carbon-400 shrink-0 mt-0.5" />
                      <div className="space-y-1">
                        <span className="text-4xs uppercase tracking-widest text-carbon-500 block font-semibold">
                          AI Tespit Gerekçesi (Linguistic Reasoning)
                        </span>
                        <p className="text-2xs text-carbon-300 leading-relaxed font-mono">
                          {item.fail_reason}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Expanded linguistic detail indicators */}
                  {isExpanded && (
                    <div className="pt-3 border-t border-hair border-carbon-800 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="space-y-2">
                        <h5 className="text-3xs uppercase tracking-wider text-carbon-450 font-semibold">
                          Dilbilimsel Sapma ve Negasyon Detayları
                        </h5>
                        <div className="space-y-1 text-2xs bg-carbon-950/20 p-2.5 border border-hair border-carbon-800">
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Negasyon Tipi:</span>
                            <span className="font-mono text-carbon-200">
                              {item.negation_type || 'Belirtilmemiş'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Negasyon Kapsamı (Scope):</span>
                            <span className="font-mono text-carbon-200">
                              {item.negation_scope || 'Yok'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Dilbilimsel Belirteç:</span>
                            <span className="font-mono text-carbon-200">
                              {item.linguistic_marker || 'Yok'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-3xs uppercase tracking-wider text-carbon-450 font-semibold">
                          Bağlamsal & Zamansal Faktör Analizi
                        </h5>
                        <div className="space-y-1 text-2xs bg-carbon-950/20 p-2.5 border border-hair border-carbon-800">
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Bağlamsal Faktör:</span>
                            <span className="font-mono text-carbon-200">
                              {item.contextual_factor || 'Belirtilmemiş'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Zamansal Değişim (Temporal):</span>
                            <span className="font-mono text-carbon-200">
                              {item.temporal_factor || 'Yok'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-carbon-400">Anomali Bağlantı Kodu:</span>
                            <span className="font-mono text-carbon-200">
                              {item.anomaly_types || 'Yok'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Expand / Collapsible action button */}
                  <div className="flex justify-end pt-1">
                    <button
                      type="button"
                      onClick={() => toggleExpand(item.fail_id)}
                      className="text-3xs flex items-center gap-1 text-carbon-400 hover:text-carbon-200 transition-colors uppercase tracking-wider font-semibold"
                    >
                      {isExpanded ? (
                        <>
                          Detayları Kapat
                          <ChevronUp className="w-3.5 h-3.5" />
                        </>
                      ) : (
                        <>
                          Linguistik Detayları Göster
                          <ChevronDown className="w-3.5 h-3.5" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
