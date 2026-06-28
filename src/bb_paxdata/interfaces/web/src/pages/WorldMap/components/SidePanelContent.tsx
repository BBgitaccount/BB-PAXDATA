import { AlertTriangle, ChevronRight, Globe, TrendingUp } from 'lucide-react';
import React from 'react';
import { GeoPanel } from '../../../components/GeoPanel';
import { SentimentBar } from '../../../components/SentimentBar';
import { useVizStore } from '../../../store/vizStore';

const SESSION_LABELS: Record<string, string> = {
  'session-1': 'Oturum 1',
  'session-2': 'Oturum 2',
  'session-3': 'Oturum 3',
  'session-4': 'Oturum 4',
  'session-5': 'Oturum 5',
};

export const SidePanelContent: React.FC = () => {
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
      <GeoPanel title="Analiz Edilen Oturumlar">
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
                    className="text-sm"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
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

      {/* Selected Country Stats */}
      {selectedCountry && selectedCountryNode && (
        <GeoPanel
          title={`${selectedCountryNode.country} (${selectedCountryNode.isoAlpha3})`}
          badge="LIVE"
        >
          <div className="space-y-4">
            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div
                className="p-3 rounded"
                style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
              >
                <div className="geoint-data-label">Avg Sentiment</div>
                <div
                  className="geoint-data-value"
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
                className="p-3 rounded"
                style={{ backgroundColor: 'var(--geoint-deep)', border: 'var(--border-subtle)' }}
              >
                <div className="geoint-data-label">Mansiyon</div>
                <div className="geoint-data-value">{selectedCountryNode.totalInteractions}</div>
              </div>
            </div>

            {/* Sentiment Bar */}
            <div>
              <div className="geoint-data-label mb-2">Sentiment Trend</div>
              <SentimentBar score={selectedCountryNode.avgSentiment} />
            </div>

            {/* Quick Allies */}
            {countryAllies.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4" style={{ color: 'var(--sentiment-ally)' }} />
                  <div className="geoint-data-label">Müttefikler</div>
                </div>
                <div className="space-y-1">
                  {countryAllies.slice(0, 3).map((flow, i) => {
                    const other =
                      flow.fromCountry === selectedCountry ? flow.toCountry : flow.fromCountry;
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between px-2 py-1 rounded"
                        style={{ backgroundColor: 'var(--geoint-deep)' }}
                      >
                        <span
                          className="text-xs"
                          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
                        >
                          {other}
                        </span>
                        <span
                          className="text-xs font-mono"
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

            {/* Quick Rivals */}
            {countryRivals.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle
                    className="w-4 h-4"
                    style={{ color: 'var(--sentiment-adversary)' }}
                  />
                  <div className="geoint-data-label">Risk Noktaları</div>
                </div>
                <div className="space-y-1">
                  {countryRivals.slice(0, 3).map((flow, i) => {
                    const other =
                      flow.fromCountry === selectedCountry ? flow.toCountry : flow.fromCountry;
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between px-2 py-1 rounded"
                        style={{ backgroundColor: 'var(--geoint-deep)' }}
                      >
                        <span
                          className="text-xs"
                          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}
                        >
                          {other}
                        </span>
                        <span
                          className="text-xs font-mono"
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

            {/* View Details Button */}
            <button
              onClick={() => {
                // This would open the full drawer - for now it's a placeholder
                console.log('Open full drawer for', selectedCountry);
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded transition-colors"
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
              Detayları Gör
              <ChevronRight className="w-4 h-4" />
            </button>
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
