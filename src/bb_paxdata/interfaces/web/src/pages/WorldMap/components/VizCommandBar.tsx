// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/VizCommandBar.tsx

import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, ChevronUp, RotateCcw, Search, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { COUNTRIES } from '../../../constants/countries';
import { useVizStore } from '../../../store/vizStore';

// Session labels
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

interface VizCommandBarProps {
  mapContainerRef?: React.RefObject<HTMLDivElement>;
}

export const VizCommandBar = ({ mapContainerRef: _mapContainerRef }: VizCommandBarProps) => {
  const { filters, setFilter, resetFilters, setHighlightedCountry } = useVizStore();

  const [countrySearch, setCountrySearch] = useState('');
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);

  const sessionDebounceRef = useRef<NodeJS.Timeout>();

  // URL serialization on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('sessions')) {
      const sessions = params.get('sessions')?.split(',') || [];
      setFilter('selectedSessions', sessions);
    }
  }, [setFilter]);

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
  }, [resetFilters]);

  // Filtered countries for search
  const filteredCountries = useMemo(() => {
    if (!countrySearch.trim()) return COUNTRIES.slice(0, 10);
    const search = countrySearch.toLowerCase();
    return COUNTRIES.filter(
      (c) => c.name.toLowerCase().includes(search) || c.id.toLowerCase().includes(search),
    ).slice(0, 10);
  }, [countrySearch]);

  const hasActiveFilters = useMemo(() => {
    return filters.selectedSessions.length > 0;
  }, [filters]);

  const selectedSessionCount = filters.selectedSessions.length;

  return (
    <div className="flex items-center gap-2">
      {/* Country Search */}
      <div className="relative">
        <div
          className="flex items-center gap-1.5 px-2 py-1 rounded"
          style={{ backgroundColor: 'var(--geoint-base)', border: 'var(--border-subtle)' }}
        >
          <Search className="w-3 h-3" style={{ color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            placeholder="Ülke ara..."
            value={countrySearch}
            onChange={(e) => setCountrySearch(e.target.value)}
            onFocus={() => setCountryDropdownOpen(true)}
            onBlur={() => setTimeout(() => setCountryDropdownOpen(false), 150)}
            className="bg-transparent border-none outline-none text-xs w-24 placeholder:text-[var(--text-tertiary)]"
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
              <X className="w-2.5 h-2.5" />
            </button>
          )}
        </div>

        <AnimatePresence>
          {countryDropdownOpen && filteredCountries.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute bottom-full left-0 mb-2 rounded shadow-xl z-50 w-64 max-h-64 overflow-y-auto geoint-scroll"
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

      {/* Session Filter - Compact */}
      <button
        onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
        className="flex items-center gap-1.5 px-2 py-1 text-xs rounded transition-colors"
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
        <span>OTURUM</span>
        {selectedSessionCount > 0 && (
          <span
            className="text-[9px] px-1 rounded"
            style={{
              backgroundColor: 'var(--signal-info)',
              color: '#000',
            }}
          >
            {selectedSessionCount}
          </span>
        )}
        {sessionDropdownOpen ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )}
      </button>

      <AnimatePresence>
        {sessionDropdownOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute bottom-full left-0 mb-2 rounded shadow-xl z-50 w-80 max-h-80 overflow-y-auto geoint-scroll"
            style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
          >
            <div className="p-2 flex gap-2" style={{ borderBottom: 'var(--border-subtle)' }}>
              <button
                onClick={handleSelectAllSessions}
                className="text-xs"
                style={{ color: 'var(--signal-info)', fontFamily: 'var(--font-label)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--sentiment-partner)')}
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

      {/* Reset Button */}
      {hasActiveFilters && (
        <button
          onClick={handleReset}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors"
          style={{
            backgroundColor: 'var(--geoint-base)',
            border: 'var(--border-subtle)',
            color: 'var(--text-tertiary)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--text-primary)';
            e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--text-tertiary)';
            e.currentTarget.style.backgroundColor = 'var(--geoint-base)';
          }}
          title="Filtreleri Sıfırla"
        >
          <RotateCcw className="w-3 h-3" />
        </button>
      )}
    </div>
  );
};
