// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/VizCommandBar.tsx

import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, ChevronUp, RotateCcw, Save, Search, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { COUNTRIES } from '../../../constants/countries';
import { useVizStore } from '../../../store/vizStore';
import type { RelationshipType } from '../../../types/visualization';
import { RELATIONSHIP_COLORS } from '../../../utils/visualizationHelpers';
import { ExportPanel } from './ExportPanel';

// Session labels from SessionTimelinePanel
const SESSION_LABELS: Record<string, string> = {
  '01_ahmed_al-sharaa': 'Ahmed Al-Sharaa Röportajı',
  '02_cevdet_yılmaz': 'Cevdet Yılmaz Açılış Konuşması',
  '03_erdoğan': 'Erdoğan Konuşması',
  '04_avrupa_başkanları': 'Avrupa Liderleri Paneli',
  '05_gazze_konuşması': 'Gazze Konuşması',
  '06_mevlüt_çavuşoğlu_ve_cumhurbaşkanları': 'Çavuşoğlu & Cumhurbaşkanları',
  '07_sergei_lavrov': 'Lavrov Konuşması',
  '08_somali': 'Somali Zirvesi',
  '09_tom_barrack': 'Tom Barrack Açıklaması',
  '10_ukrayna_dışişleri_bakanı': 'Ukrayna Dışişleri Bakanı',
  '11_hakan_fidan': 'Hakan Fidan Açıklaması',
  '12_climate': 'İklim Görüşmeleri',
};

const SESSION_IDS = Object.keys(SESSION_LABELS);

// ISO flag emoji mapping
const getFlagEmoji = (countryId: string): string => {
  const flagMap: Record<string, string> = {
    TUR: '🇹🇷',
    USA: '🇺🇸',
    RUS: '🇷🇺',
    CHN: '🇨🇳',
    DEU: '🇩🇪',
    FRA: '🇫🇷',
    GBR: '🇬🇧',
    IRN: '🇮🇷',
    ISR: '🇮🇱',
    SAU: '🇸🇦',
    IND: '🇮🇳',
    BRA: '🇧🇷',
    ZAF: '🇿🇦',
    JPN: '🇯🇵',
    KOR: '🇰🇷',
  };
  return flagMap[countryId] || '🏳️';
};

interface MapLayers {
  choropleth: boolean;
  arcs: boolean;
  bubbles: boolean;
  hotspots: boolean;
}

const DEFAULT_LAYERS: MapLayers = {
  choropleth: true,
  arcs: true,
  bubbles: true,
  hotspots: true,
};

interface VizCommandBarProps {
  mapContainerRef?: React.RefObject<HTMLDivElement>;
}

export const VizCommandBar = ({ mapContainerRef }: VizCommandBarProps) => {
  const { filters, setFilter, resetFilters, setHighlightedCountry } = useVizStore();

  // Local state for UI controls
  const [countrySearch, setCountrySearch] = useState('');
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const [layers, setLayers] = useState<MapLayers>(DEFAULT_LAYERS);
  const [mobileExpanded, setMobileExpanded] = useState(false);

  // Refs for debounce/throttle
  const countrySearchRef = useRef<string>('');
  const sessionDebounceRef = useRef<NodeJS.Timeout>();
  const sliderThrottleRef = useRef<NodeJS.Timeout>();

  // URL serialization on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('sessions')) {
      const sessions = params.get('sessions')?.split(',') || [];
      setFilter('selectedSessions', sessions);
    }
    if (params.has('relTypes')) {
      const relTypes = params.get('relTypes')?.split(',') as RelationshipType[];
      setFilter('selectedRelTypes', relTypes);
    }
    if (params.has('minInteractions')) {
      const minInteractions = parseInt(params.get('minInteractions') || '2');
      setFilter('minInteractions', minInteractions);
    }
    if (params.has('layers')) {
      const layersParam = params.get('layers')?.split(',') || [];
      setLayers({
        choropleth: layersParam.includes('choropleth'),
        arcs: layersParam.includes('arcs'),
        bubbles: layersParam.includes('bubbles'),
        hotspots: layersParam.includes('hotspots'),
      });
    }
  }, [setFilter]);

  // Debounced country search
  const handleCountrySearchChange = useCallback((value: string) => {
    setCountrySearch(value);
    countrySearchRef.current = value;
  }, []);

  // Debounced session filter
  const handleSessionToggle = useCallback(
    (sessionId: string) => {
      if (sessionDebounceRef.current) {
        clearTimeout(sessionDebounceRef.current);
      }

      sessionDebounceRef.current = setTimeout(() => {
        const currentSessions = filters.selectedSessions;
        const newSessions = currentSessions.includes(sessionId)
          ? currentSessions.filter((s) => s !== sessionId)
          : [...currentSessions, sessionId];
        setFilter('selectedSessions', newSessions);
      }, 150);
    },
    [filters.selectedSessions, setFilter],
  );

  const handleSelectAllSessions = useCallback(() => {
    setFilter('selectedSessions', SESSION_IDS);
  }, [setFilter]);

  const handleClearAllSessions = useCallback(() => {
    setFilter('selectedSessions', []);
  }, [setFilter]);

  // Throttled slider
  const handleMinInteractionChange = useCallback(
    (value: number) => {
      if (sliderThrottleRef.current) {
        clearTimeout(sliderThrottleRef.current);
      }

      sliderThrottleRef.current = setTimeout(() => {
        setFilter('minInteractions', value);
      }, 100);
    },
    [setFilter],
  );

  // Relationship type toggle
  const handleRelTypeToggle = useCallback(
    (relType: RelationshipType) => {
      const currentTypes = filters.selectedRelTypes;
      const newTypes = currentTypes.includes(relType)
        ? currentTypes.filter((t) => t !== relType)
        : [...currentTypes, relType];
      setFilter('selectedRelTypes', newTypes);
    },
    [filters.selectedRelTypes, setFilter],
  );

  // Layer toggle
  const handleLayerToggle = useCallback((layer: keyof MapLayers) => {
    setLayers((prev) => ({ ...prev, [layer]: !prev[layer] }));
  }, []);

  // Country selection
  const handleCountrySelect = useCallback(
    (countryId: string) => {
      setHighlightedCountry(countryId);
      setCountrySearch('');
      setCountryDropdownOpen(false);
    },
    [setHighlightedCountry],
  );

  // Reset all filters
  const handleReset = useCallback(() => {
    resetFilters();
    setCountrySearch('');
    setLayers(DEFAULT_LAYERS);
  }, [resetFilters]);

  // Save filters to URL
  const handleSaveToUrl = useCallback(() => {
    const params = new URLSearchParams();

    if (filters.selectedSessions.length > 0) {
      params.set('sessions', filters.selectedSessions.join(','));
    }
    if (filters.selectedRelTypes.length > 0) {
      params.set('relTypes', filters.selectedRelTypes.join(','));
    }
    if (filters.minInteractions !== 2) {
      params.set('minInteractions', filters.minInteractions.toString());
    }

    const activeLayers = Object.entries(layers)
      .filter(([_, active]) => active)
      .map(([layer]) => layer);
    if (activeLayers.length > 0 && activeLayers.length < 4) {
      params.set('layers', activeLayers.join(','));
    }

    const url = `${window.location.pathname}?${params.toString()}`;
    navigator.clipboard.writeText(window.location.origin + url);
  }, [filters, layers]);

  // Filtered countries for search
  const filteredCountries = useMemo(() => {
    if (!countrySearch.trim()) return COUNTRIES.slice(0, 10);
    const search = countrySearch.toLowerCase();
    return COUNTRIES.filter(
      (c) => c.name.toLowerCase().includes(search) || c.id.toLowerCase().includes(search),
    ).slice(0, 10);
  }, [countrySearch]);

  // Active filter summary
  const activeFilterSummary = useMemo(() => {
    const parts: string[] = [];
    if (filters.selectedSessions.length > 0) {
      parts.push(`${filters.selectedSessions.length} oturum`);
    }
    if (filters.selectedRelTypes.length > 0) {
      parts.push(filters.selectedRelTypes.join('+'));
    }
    if (filters.minInteractions > 2) {
      parts.push(`min.${filters.minInteractions}`);
    }
    return parts.join(', ');
  }, [filters]);

  const hasActiveFilters = useMemo(() => {
    return (
      filters.selectedSessions.length > 0 ||
      filters.selectedRelTypes.length > 0 ||
      filters.minInteractions > 2
    );
  }, [filters]);

  const selectedSessionCount = filters.selectedSessions.length;

  return (
    <div style={{ backgroundColor: 'var(--geoint-base)', borderBottom: 'var(--border-subtle)' }}>
      {/* Desktop Layout */}
      <div className="hidden md:block">
        <div className="flex items-center gap-4 px-4 py-3">
          {/* Country Search */}
          <div className="relative">
            <div
              className="flex items-center gap-2 px-3 py-2"
              style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
            >
              <Search className="w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
              <input
                type="text"
                placeholder="Ülke ara..."
                value={countrySearch}
                onChange={(e) => handleCountrySearchChange(e.target.value)}
                onFocus={() => setCountryDropdownOpen(true)}
                onBlur={() => setTimeout(() => setCountryDropdownOpen(false), 150)}
                className="bg-transparent border-none outline-none text-sm w-40 placeholder:text-[var(--text-tertiary)]"
                style={{
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                }}
              />
              {countrySearch && (
                <button
                  onClick={() => setCountrySearch('')}
                  style={{ color: 'var(--text-tertiary)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <AnimatePresence>
              {countryDropdownOpen && filteredCountries.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute top-full left-0 mt-1 rounded shadow-xl z-50 w-64 max-h-64 overflow-y-auto geoint-scroll"
                  style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
                >
                  {filteredCountries.map((country) => (
                    <button
                      key={country.id}
                      onClick={() => handleCountrySelect(country.id)}
                      className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors"
                      style={{
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                        e.currentTarget.style.color = 'var(--text-primary)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = 'var(--text-secondary)';
                      }}
                    >
                      <span className="text-lg">{getFlagEmoji(country.id)}</span>
                      <span>{country.name}</span>
                      <span className="text-xs ml-auto" style={{ color: 'var(--text-tertiary)' }}>
                        {country.id}
                      </span>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Session Filter */}
          <div className="relative">
            <button
              onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 text-sm transition-colors"
              style={{
                backgroundColor: 'var(--geoint-deep)',
                border: 'var(--border-subtle)',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-label)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                e.currentTarget.style.color = 'var(--text-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--geoint-deep)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              <span>OTURUM:</span>
              <span style={{ color: 'var(--text-tertiary)' }}>
                {selectedSessionCount === 0 ? 'Tümü' : `${selectedSessionCount} seçili`}
              </span>
              {selectedSessionCount > 0 && (
                <span
                  className="text-xs px-1.5"
                  style={{
                    backgroundColor: 'var(--signal-info)',
                    color: '#000',
                    borderRadius: '2px',
                  }}
                >
                  {selectedSessionCount}
                </span>
              )}
              {sessionDropdownOpen ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>

            <AnimatePresence>
              {sessionDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute top-full left-0 mt-1 rounded shadow-xl z-50 w-80 max-h-80 overflow-y-auto geoint-scroll"
                  style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
                >
                  <div className="p-2 flex gap-2" style={{ borderBottom: 'var(--border-subtle)' }}>
                    <button
                      onClick={handleSelectAllSessions}
                      className="text-xs"
                      style={{ color: 'var(--signal-info)', fontFamily: 'var(--font-label)' }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.color = 'var(--sentiment-partner)')
                      }
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--signal-info)')}
                    >
                      Tümünü Seç
                    </button>
                    <button
                      onClick={handleClearAllSessions}
                      className="text-xs"
                      style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-label)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
                    >
                      Temizle
                    </button>
                  </div>
                  {SESSION_IDS.map((sessionId) => {
                    const isSelected = filters.selectedSessions.includes(sessionId);
                    return (
                      <button
                        key={sessionId}
                        onClick={() => handleSessionToggle(sessionId)}
                        className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors ${
                          isSelected ? '' : ''
                        }`}
                        style={{
                          backgroundColor: isSelected ? 'var(--geoint-elevated)' : 'transparent',
                          fontFamily: 'var(--font-mono)',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) {
                            e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          readOnly
                          className="w-4 h-4 rounded"
                          style={{
                            border: 'var(--border-subtle)',
                            backgroundColor: 'var(--geoint-deep)',
                            accentColor: 'var(--signal-info)',
                          }}
                        />
                        <span
                          style={{
                            color: isSelected ? 'var(--text-primary)' : 'var(--text-tertiary)',
                          }}
                        >
                          {SESSION_LABELS[sessionId] || sessionId}
                        </span>
                      </button>
                    );
                  })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Relationship Type Toggles */}
          <div className="flex items-center gap-2">
            <span
              className="text-xs mr-1"
              style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
            >
              İLİŞKİ:
            </span>
            {(Object.keys(RELATIONSHIP_COLORS) as RelationshipType[]).map((relType) => {
              const isActive = filters.selectedRelTypes.includes(relType);
              const color = RELATIONSHIP_COLORS[relType];
              return (
                <button
                  key={relType}
                  onClick={() => handleRelTypeToggle(relType)}
                  className="px-2 py-1 text-xs font-medium rounded transition-all"
                  style={
                    isActive
                      ? { backgroundColor: color, color: '#000' }
                      : {
                          color: 'var(--text-tertiary)',
                          border: 'var(--border-subtle)',
                          fontFamily: 'var(--font-label)',
                        }
                  }
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.color = 'var(--text-secondary)';
                      e.currentTarget.style.borderColor = 'var(--text-tertiary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.color = 'var(--text-tertiary)';
                      e.currentTarget.style.borderColor = 'var(--geoint-border)';
                    }
                  }}
                >
                  {relType}
                </button>
              );
            })}
          </div>

          {/* Map Layers */}
          <div
            className="flex items-center gap-3 pl-4"
            style={{ borderLeft: 'var(--border-subtle)' }}
          >
            <span
              className="text-xs"
              style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
            >
              Katman:
            </span>
            {Object.entries(layers).map(([layer, active]) => (
              <label key={layer} className="flex items-center gap-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => handleLayerToggle(layer as keyof MapLayers)}
                  className="w-4 h-4 rounded"
                  style={{
                    border: 'var(--border-subtle)',
                    backgroundColor: 'var(--geoint-deep)',
                    accentColor: 'var(--signal-info)',
                  }}
                />
                <span
                  className="text-xs capitalize"
                  style={{ fontFamily: 'var(--font-label)', color: 'var(--text-secondary)' }}
                >
                  {layer === 'choropleth' ? 'Renk' : layer}
                </span>
              </label>
            ))}
          </div>

          {/* Min Interaction Slider */}
          <div
            className="flex items-center gap-3 pl-4"
            style={{ borderLeft: 'var(--border-subtle)' }}
          >
            <span
              className="text-xs"
              style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
            >
              Min.İnteraksiyon:
            </span>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="1"
                max="50"
                value={filters.minInteractions}
                onChange={(e) => handleMinInteractionChange(parseInt(e.target.value))}
                className="w-24"
                style={
                  {
                    '--range-progress': `${((filters.minInteractions - 1) / 49) * 100}%`,
                  } as React.CSSProperties
                }
              />
              <span
                className="text-sm w-8 text-center font-mono"
                style={{ color: 'var(--text-primary)' }}
              >
                {filters.minInteractions}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 ml-auto">
            {hasActiveFilters && (
              <>
                <span
                  className="text-xs"
                  style={{ fontFamily: 'var(--font-label)', color: 'var(--signal-info)' }}
                >
                  AKTİF FİLTRE: {activeFilterSummary}
                </span>
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1 px-3 py-2 text-sm rounded transition-colors"
                  style={{
                    color: 'var(--text-tertiary)',
                    fontFamily: 'var(--font-label)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--text-primary)';
                    e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-tertiary)';
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <RotateCcw className="w-4 h-4" />
                  Sıfırla
                </button>
              </>
            )}
            <button
              onClick={handleSaveToUrl}
              className="flex items-center gap-1 px-3 py-2 text-sm rounded transition-colors"
              style={{
                color: 'var(--text-tertiary)',
                fontFamily: 'var(--font-label)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--text-primary)';
                e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-tertiary)';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
              title="URL'ye kaydet"
            >
              <Save className="w-4 h-4" />
              Kaydet
            </button>
            <ExportPanel mapContainerRef={mapContainerRef} />
          </div>
        </div>
      </div>

      {/* Mobile Layout */}
      <div className="md:hidden">
        <div className="px-4 py-3">
          <button
            onClick={() => setMobileExpanded(!mobileExpanded)}
            className="w-full flex items-center justify-between text-sm"
            style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-label)' }}
          >
            <span>Filtreler</span>
            {hasActiveFilters && (
              <span className="text-xs mr-2" style={{ color: 'var(--signal-info)' }}>
                {activeFilterSummary}
              </span>
            )}
            {mobileExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          <AnimatePresence>
            {mobileExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-4 space-y-4">
                  {/* Country Search */}
                  <div
                    className="flex items-center gap-2 px-3 py-2"
                    style={{
                      backgroundColor: 'var(--geoint-deep)',
                      border: 'var(--border-subtle)',
                    }}
                  >
                    <Search className="w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="text"
                      placeholder="Ülke ara..."
                      value={countrySearch}
                      onChange={(e) => handleCountrySearchChange(e.target.value)}
                      className="bg-transparent border-none outline-none text-sm flex-1"
                      style={{
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    />
                    {countrySearch && (
                      <button
                        onClick={() => setCountrySearch('')}
                        style={{ color: 'var(--text-tertiary)' }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.color = 'var(--text-secondary)')
                        }
                        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>

                  {/* Session Filter */}
                  <div>
                    <button
                      onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
                      className="w-full flex items-center justify-between px-3 py-2 text-sm"
                      style={{
                        backgroundColor: 'var(--geoint-deep)',
                        border: 'var(--border-subtle)',
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font-label)',
                      }}
                    >
                      <span>
                        OTURUM:{' '}
                        {selectedSessionCount === 0 ? 'Tümü' : `${selectedSessionCount} seçili`}
                      </span>
                      {sessionDropdownOpen ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>

                    {sessionDropdownOpen && (
                      <div
                        className="mt-2 max-h-48 overflow-y-auto geoint-scroll"
                        style={{
                          backgroundColor: 'var(--geoint-deep)',
                          border: 'var(--border-subtle)',
                        }}
                      >
                        <div
                          className="p-2 flex gap-2"
                          style={{ borderBottom: 'var(--border-subtle)' }}
                        >
                          <button
                            onClick={handleSelectAllSessions}
                            className="text-xs"
                            style={{ color: 'var(--signal-info)', fontFamily: 'var(--font-label)' }}
                          >
                            Tümünü Seç
                          </button>
                          <button
                            onClick={handleClearAllSessions}
                            className="text-xs"
                            style={{
                              color: 'var(--text-tertiary)',
                              fontFamily: 'var(--font-label)',
                            }}
                          >
                            Temizle
                          </button>
                        </div>
                        {SESSION_IDS.map((sessionId) => {
                          const isSelected = filters.selectedSessions.includes(sessionId);
                          return (
                            <button
                              key={sessionId}
                              onClick={() => handleSessionToggle(sessionId)}
                              className="w-full px-3 py-2 text-left text-sm flex items-center gap-2"
                              style={{
                                backgroundColor: isSelected
                                  ? 'var(--geoint-elevated)'
                                  : 'transparent',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                readOnly
                                className="w-4 h-4 rounded"
                                style={{
                                  border: 'var(--border-subtle)',
                                  backgroundColor: 'var(--geoint-deep)',
                                  accentColor: 'var(--signal-info)',
                                }}
                              />
                              <span
                                style={{
                                  color: isSelected
                                    ? 'var(--text-primary)'
                                    : 'var(--text-tertiary)',
                                }}
                              >
                                {SESSION_LABELS[sessionId] || sessionId}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Relationship Type Toggles */}
                  <div>
                    <span
                      className="text-xs block mb-2"
                      style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
                    >
                      İLİŞKİ:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {(Object.keys(RELATIONSHIP_COLORS) as RelationshipType[]).map((relType) => {
                        const isActive = filters.selectedRelTypes.includes(relType);
                        const color = RELATIONSHIP_COLORS[relType];
                        return (
                          <button
                            key={relType}
                            onClick={() => handleRelTypeToggle(relType)}
                            className="px-2 py-1 text-xs font-medium rounded"
                            style={
                              isActive
                                ? { backgroundColor: color, color: '#000' }
                                : {
                                    color: 'var(--text-tertiary)',
                                    border: 'var(--border-subtle)',
                                    fontFamily: 'var(--font-label)',
                                  }
                            }
                          >
                            {relType}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Map Layers */}
                  <div>
                    <span
                      className="text-xs block mb-2"
                      style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
                    >
                      Katman:
                    </span>
                    <div className="flex flex-wrap gap-3">
                      {Object.entries(layers).map(([layer, active]) => (
                        <label key={layer} className="flex items-center gap-1 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={active}
                            onChange={() => handleLayerToggle(layer as keyof MapLayers)}
                            className="w-4 h-4 rounded"
                            style={{
                              border: 'var(--border-subtle)',
                              backgroundColor: 'var(--geoint-deep)',
                              accentColor: 'var(--signal-info)',
                            }}
                          />
                          <span
                            className="text-xs capitalize"
                            style={{
                              fontFamily: 'var(--font-label)',
                              color: 'var(--text-secondary)',
                            }}
                          >
                            {layer === 'choropleth' ? 'Renk' : layer}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Min Interaction Slider */}
                  <div>
                    <span
                      className="text-xs block mb-2"
                      style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
                    >
                      Min.İnteraksiyon:
                    </span>
                    <div className="flex items-center gap-2">
                      <input
                        type="range"
                        min="1"
                        max="50"
                        value={filters.minInteractions}
                        onChange={(e) => handleMinInteractionChange(parseInt(e.target.value))}
                        className="flex-1"
                        style={
                          {
                            '--range-progress': `${((filters.minInteractions - 1) / 49) * 100}%`,
                          } as React.CSSProperties
                        }
                      />
                      <span
                        className="text-sm w-8 text-center font-mono"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {filters.minInteractions}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-2" style={{ borderTop: 'var(--border-subtle)' }}>
                    {hasActiveFilters && (
                      <button
                        onClick={handleReset}
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-2 text-sm rounded transition-colors"
                        style={{
                          color: 'var(--text-tertiary)',
                          fontFamily: 'var(--font-label)',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = 'var(--text-primary)';
                          e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = 'var(--text-tertiary)';
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }}
                      >
                        <RotateCcw className="w-4 h-4" />
                        Sıfırla
                      </button>
                    )}
                    <button
                      onClick={handleSaveToUrl}
                      className="flex-1 flex items-center justify-center gap-1 px-3 py-2 text-sm rounded transition-colors"
                      style={{
                        color: 'var(--text-tertiary)',
                        fontFamily: 'var(--font-label)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'var(--text-primary)';
                        e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--text-tertiary)';
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <Save className="w-4 h-4" />
                      Kaydet
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
