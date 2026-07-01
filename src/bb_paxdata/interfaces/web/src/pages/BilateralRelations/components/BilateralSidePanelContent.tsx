import { AlertTriangle, Globe, TrendingUp } from 'lucide-react';
import React from 'react';
import { GeoPanel } from '../../../components/GeoPanel';
import { SentimentBar } from '../../../components/SentimentBar';
import { useVizStore } from '../../../store/vizStore';

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

export const BilateralSidePanelContent: React.FC = () => {
  const { filters, data, setFilter } = useVizStore();
  const { selectedSessions, selectedCountry } = filters;
  const { countryNodes, bilateralFlows } = data;

  // Get unique sessions from data
  const availableSessions = Array.from(new Set([...data.sessionTimeline.map((s) => s.sessionId)]));

  // Find selected country node
  const selectedCountryNode = selectedCountry
    ? countryNodes.find((n) => n.country === selectedCountry)
    : null;

  // Get allies and rivals for selected country
  const countryAllies = bilateralFlows
    .filter(
      (c) =>
        (c.fromCountry === selectedCountry || c.toCountry === selectedCountry) &&
        c.affinityScore > 0.3,
    )
    .sort((a, b) => b.affinityScore - a.affinityScore)
    .slice(0, 5);

  const countryRivals = bilateralFlows
    .filter(
      (c) =>
        (c.fromCountry === selectedCountry || c.toCountry === selectedCountry) &&
        c.affinityScore < -0.3,
    )
    .sort((a, b) => a.affinityScore - b.affinityScore)
    .slice(0, 5);

  const handleSessionClick = (sessionId: string) => {
    const newSelected = selectedSessions.includes(sessionId)
      ? selectedSessions.filter((s) => s !== sessionId)
      : [...selectedSessions, sessionId];
    setFilter('selectedSessions', newSelected);
  };

  return (
    <div className="space-y-4 p-4">
      {/* Session List */}
      <GeoPanel
        title="Analiz Edilen Oturumlar"
        badge={`${selectedSessions.length}/${availableSessions.length}`}
      >
        <div className="space-y-2">
          {availableSessions.length === 0 ? (
            <p className="text-xs italic" style={{ color: 'var(--text-tertiary)' }}>
              Oturum verisi yükleniyor...
            </p>
          ) : (
            availableSessions.map((sessionId) => {
              const isSelected = selectedSessions.includes(sessionId);
              return (
                <button
                  key={sessionId}
                  onClick={() => handleSessionClick(sessionId)}
                  className="w-full text-left px-3 py-2 rounded transition-colors flex items-center justify-between"
                  style={{
                    backgroundColor: isSelected ? 'var(--geoint-elevated)' : 'var(--geoint-deep)',
                    border: isSelected ? 'var(--border-subtle)' : '1px solid transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.backgroundColor = 'var(--geoint-deep)';
                    }
                  }}
                >
                  <span
                    className="text-xs"
                    style={{
                      fontFamily: 'var(--font-mono)',
                      color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                    }}
                  >
                    {SESSION_LABELS[sessionId] || sessionId}
                  </span>
                  {isSelected && (
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: 'var(--signal-info)' }}
                    />
                  )}
                </button>
              );
            })
          )}
        </div>
      </GeoPanel>

      {/* Selected Country Stats - Quick Preview */}
      {selectedCountry && selectedCountryNode && (
        <GeoPanel title={`${selectedCountryNode.country}`} badge="ÖNİZLEME">
          <div className="space-y-3">
            {/* Quick Stats Row */}
            <div className="grid grid-cols-2 gap-2">
              <div
                className="p-2 rounded"
                style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
              >
                <div className="geoint-data-label text-[9px]">Sentiment</div>
                <div
                  className="geoint-data-value text-xs"
                  style={{
                    color:
                      selectedCountryNode.avgSentiment > 0.3
                        ? 'var(--sentiment-ally)'
                        : selectedCountryNode.avgSentiment < -0.3
                          ? 'var(--sentiment-adversary)'
                          : 'var(--sentiment-neutral)',
                  }}
                >
                  {selectedCountryNode.avgSentiment.toFixed(2)}
                </div>
              </div>
              <div
                className="p-2 rounded"
                style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
              >
                <div className="geoint-data-label text-[9px]">Mansiyon</div>
                <div className="geoint-data-value text-xs">
                  {selectedCountryNode.totalInteractions}
                </div>
              </div>
            </div>

            {/* Sentiment Bar */}
            <div>
              <SentimentBar score={selectedCountryNode.avgSentiment} />
            </div>

            {/* Quick Allies/Rivals */}
            {countryAllies.length > 0 && (
              <div>
                <div className="flex items-center gap-1 mb-1">
                  <TrendingUp className="w-3 h-3" style={{ color: 'var(--sentiment-ally)' }} />
                  <div className="geoint-data-label text-[10px]">Müttefikler</div>
                </div>
                <div className="space-y-0.5">
                  {countryAllies.slice(0, 2).map((flow, i) => {
                    const other =
                      flow.fromCountry === selectedCountry ? flow.toCountry : flow.fromCountry;
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between px-2 py-0.5 rounded"
                        style={{ backgroundColor: 'var(--geoint-deep)' }}
                      >
                        <span
                          className="text-[10px]"
                          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
                        >
                          {other}
                        </span>
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: 'var(--sentiment-ally)' }}
                        >
                          +{flow.affinityScore.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {countryRivals.length > 0 && (
              <div>
                <div className="flex items-center gap-1 mb-1">
                  <AlertTriangle
                    className="w-3 h-3"
                    style={{ color: 'var(--sentiment-adversary)' }}
                  />
                  <div className="geoint-data-label text-[10px]">Riskler</div>
                </div>
                <div className="space-y-0.5">
                  {countryRivals.slice(0, 2).map((flow, i) => {
                    const other =
                      flow.fromCountry === selectedCountry ? flow.toCountry : flow.fromCountry;
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between px-2 py-0.5 rounded"
                        style={{ backgroundColor: 'var(--geoint-deep)' }}
                      >
                        <span
                          className="text-[10px]"
                          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
                        >
                          {other}
                        </span>
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: 'var(--sentiment-adversary)' }}
                        >
                          {flow.affinityScore.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </GeoPanel>
      )}

      {/* No Country Selected */}
      {!selectedCountry && (
        <div
          className="p-6 text-center rounded"
          style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
        >
          <Globe className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
          <p
            className="text-sm"
            style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
          >
            Haritadan bir ülke seçin
          </p>
          <p
            className="text-xs mt-1"
            style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
          >
            Detaylı analiz için
          </p>
        </div>
      )}
    </div>
  );
};
