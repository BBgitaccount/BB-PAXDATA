// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/ExportPanel.tsx

import { saveAs } from 'file-saver';
import html2canvas from 'html2canvas';
import { Download, FileText, Image, Loader2, Printer, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '../../../services/apiClient';
import { useVizStore } from '../../../store/vizStore';
import type { BilateralFlow, CountryNode } from '../../../types/visualization';

interface ExportPanelProps {
  mapContainerRef?: React.RefObject<HTMLDivElement>;
  onExportStart?: () => void;
  onExportEnd?: () => void;
}

interface BriefData {
  totalInteractions: number;
  topAlliances: BilateralFlow[];
  topAdversaries: BilateralFlow[];
  avgGlobalSentiment: number;
  activeSessions: string[];
  highRiskCountries: CountryNode[];
}

export const ExportPanel: React.FC<ExportPanelProps> = ({
  mapContainerRef,
  onExportStart,
  onExportEnd,
}) => {
  const { data: vizData, filters } = useVizStore();
  const [isExporting, setIsExporting] = useState(false);
  const [isGeneratingBrief, setIsGeneratingBrief] = useState(false);
  const [briefModalOpen, setBriefModalOpen] = useState(false);
  const [generatedBrief, setGeneratedBrief] = useState('');
  const [typewriterText, setTypewriterText] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const typewriterRef = useRef<NodeJS.Timeout | null>(null);

  // Typewriter effect for AI brief
  useEffect(() => {
    if (briefModalOpen && generatedBrief) {
      setTypewriterText('');
      let index = 0;
      const text = generatedBrief;

      const typeNextChar = () => {
        if (index < text.length) {
          setTypewriterText(text.slice(0, index + 1));
          index++;
          typewriterRef.current = setTimeout(typeNextChar, 15);
        }
      };

      typeNextChar();
    }

    return () => {
      if (typewriterRef.current) {
        clearTimeout(typewriterRef.current);
      }
    };
  }, [briefModalOpen, generatedBrief]);

  // PNG Export with watermark
  const exportAsPNG = useCallback(async () => {
    if (!mapContainerRef?.current) return;

    setIsExporting(true);
    onExportStart?.();

    try {
      const canvas = await html2canvas(mapContainerRef.current, {
        scale: 2,
        backgroundColor: '#0a0f1a',
        logging: false,
      });

      // Add watermark
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.font = 'bold 24px JetBrains Mono, monospace';
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.fillText('BB-PAXDATA', 20, 40);
        ctx.font = '14px JetBrains Mono, monospace';
        ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.fillText(new Date().toLocaleDateString('tr-TR'), 20, 65);
      }

      canvas.toBlob((blob) => {
        if (blob) {
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
          saveAs(blob, `bb-paxdata-worldmap-${timestamp}.png`);
        }
      });
    } catch (error) {
      console.error('PNG export failed:', error);
    } finally {
      setIsExporting(false);
      onExportEnd?.();
    }
  }, [mapContainerRef, onExportStart, onExportEnd]);

  // CSV Export for bilateral flows
  const exportFlowsCSV = useCallback(() => {
    const flows = vizData.bilateralFlows;
    if (flows.length === 0) return;

    const headers = [
      'From Country',
      'To Country',
      'Relationship Type',
      'Interaction Count',
      'Avg Sentiment',
      'Affinity Score',
      'Praise Ratio',
      'Accusation Ratio',
    ];

    const rows = flows.map((f) => [
      f.fromCountry,
      f.toCountry,
      f.relationshipType,
      f.interactionCount,
      f.avgSentiment.toFixed(3),
      f.affinityScore.toFixed(3),
      f.praiseRatio.toFixed(3),
      f.accusationRatio.toFixed(3),
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filterSuffix =
      filters.selectedRelTypes.length > 0 ? filters.selectedRelTypes.join('-') : 'all';
    saveAs(blob, `bilateral-flows-${filterSuffix}-${timestamp}.csv`);
  }, [vizData.bilateralFlows, filters.selectedRelTypes]);

  // CSV Export for country nodes
  const exportNodesCSV = useCallback(() => {
    const nodes = vizData.countryNodes;
    if (nodes.length === 0) return;

    const headers = [
      'Country',
      'ISO Alpha3',
      'Total Interactions',
      'Avg Sentiment',
      'Dominant Emotion',
      'Praise Count',
      'Accusation Count',
      'Neutral Count',
      'Power Level',
      'Sessions',
    ];

    const rows = nodes.map((n) => [
      n.country,
      n.isoAlpha3 || '',
      n.totalInteractions,
      n.avgSentiment.toFixed(3),
      n.dominantEmotion || '',
      n.praiseCount,
      n.accusationCount,
      n.neutralCount,
      n.powerLevel,
      n.sessions.join(';'),
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    saveAs(blob, `country-nodes-${timestamp}.csv`);
  }, [vizData.countryNodes]);

  // AI Intelligence Brief generation
  const generateIntelligenceBrief = useCallback(async () => {
    setIsGeneratingBrief(true);
    setBriefModalOpen(true);
    setGeneratedBrief('');

    try {
      const briefData: BriefData = {
        totalInteractions: vizData.bilateralFlows.reduce((sum, f) => sum + f.interactionCount, 0),
        topAlliances: vizData.bilateralFlows
          .filter((f) => f.relationshipType === 'ALLY')
          .sort((a, b) => b.affinityScore - a.affinityScore)
          .slice(0, 5),
        topAdversaries: vizData.bilateralFlows
          .filter((f) => f.relationshipType === 'ADVERSARY')
          .sort((a, b) => a.affinityScore - b.affinityScore)
          .slice(0, 5),
        avgGlobalSentiment:
          vizData.countryNodes.reduce((sum, n) => sum + n.avgSentiment, 0) /
          (vizData.countryNodes.length || 1),
        activeSessions: filters.selectedSessions,
        highRiskCountries: vizData.countryNodes
          .filter((n) => n.accusationCount > n.praiseCount)
          .sort((a, b) => b.accusationCount - a.accusationCount)
          .slice(0, 3),
      };

      const prompt = `
Sen bir diplomatik istihbarat analistinin asistanısın. 
Aşağıdaki diplomatik söylem analiz verilerini inceleyerek 
3 paragraf halinde yönetici özeti (executive brief) hazırla.
Türkçe yaz. Akademik ama okunabilir ton kullan.

Veri:
- Toplam Etkileşim: ${briefData.totalInteractions}
- Müttefik İlişkiler: ${briefData.topAlliances.length} çift
- ADVERSARY İlişkiler: ${briefData.topAdversaries.length} çift
- Global Ortalama Sentiment: ${briefData.avgGlobalSentiment.toFixed(3)}
- En Yüksek Risk: ${briefData.highRiskCountries.map((c) => c.country).join(', ')}

İttifak bağlamı: ${JSON.stringify(briefData.topAlliances)}
Çatışma bağlamı: ${JSON.stringify(briefData.topAdversaries)}

Şu 3 başlıkta yaz:
1. GENEL DEĞERLENDİRME (mevcut diplomatik iklim)
2. KRİTİK İLİŞKİLER (öne çıkan ittifaklar ve gerilimler)
3. RİSK DEĞERLENDİRMESİ (dikkat edilmesi gereken noktalar)
`;

      const response = await apiClient.post<{ content: string }>('/api/v1/ai/intelligence-brief', {
        prompt,
        max_tokens: 800,
      });

      setGeneratedBrief(response.content);
    } catch (error) {
      console.error('AI brief generation failed:', error);
      setGeneratedBrief(
        'İstihbarat özeti oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin.',
      );
    } finally {
      setIsGeneratingBrief(false);
    }
  }, [vizData, filters.selectedSessions]);

  // Copy brief to clipboard
  const copyBriefToClipboard = useCallback(() => {
    navigator.clipboard.writeText(generatedBrief);
  }, [generatedBrief]);

  // Print as PDF
  const printAsPDF = useCallback(() => {
    window.print();
  }, []);

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded transition-colors"
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
          <Download className="w-4 h-4" />
          Export
        </button>

        {dropdownOpen && (
          <div
            className="absolute top-full right-0 mt-1 rounded shadow-xl z-50 w-56"
            style={{
              backgroundColor: 'var(--geoint-deep)',
              border: 'var(--border-subtle)',
            }}
          >
            <div className="p-1">
              <button
                onClick={() => {
                  exportAsPNG();
                  setDropdownOpen(false);
                }}
                disabled={isExporting}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm rounded transition-colors"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-label)',
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
                {isExporting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Image className="w-4 h-4" />
                )}
                PNG Olarak İndir
              </button>

              <button
                onClick={() => {
                  exportFlowsCSV();
                  setDropdownOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm rounded transition-colors"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-label)',
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
                <FileText className="w-4 h-4" />
                Bilateral Flows CSV
              </button>

              <button
                onClick={() => {
                  exportNodesCSV();
                  setDropdownOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm rounded transition-colors"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-label)',
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
                <FileText className="w-4 h-4" />
                Country Nodes CSV
              </button>

              <div className="my-1" style={{ borderBottom: 'var(--border-subtle)' }} />

              <button
                onClick={() => {
                  generateIntelligenceBrief();
                  setDropdownOpen(false);
                }}
                disabled={isGeneratingBrief}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm rounded transition-colors"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-label)',
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
                {isGeneratingBrief ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                📋 İstihbarat Özeti
              </button>

              <button
                onClick={() => {
                  printAsPDF();
                  setDropdownOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm rounded transition-colors"
                style={{
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-label)',
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
                <Printer className="w-4 h-4" />
                PDF Olarak Yazdır
              </button>
            </div>
          </div>
        )}
      </div>

      {/* AI Brief Modal */}
      {briefModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}
          onClick={() => setBriefModalOpen(false)}
        >
          <div
            className="w-full max-w-2xl rounded shadow-2xl p-6"
            style={{
              backgroundColor: 'var(--geoint-deep)',
              border: 'var(--border-subtle)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3
                className="text-lg font-bold flex items-center gap-2"
                style={{
                  fontFamily: 'var(--font-display)',
                  color: 'var(--text-primary)',
                }}
              >
                <Sparkles className="w-5 h-5 text-indigo-400" />
                Diplomatik İstihbarat Özeti
              </h3>
              <button
                onClick={() => setBriefModalOpen(false)}
                className="text-2xl"
                style={{ color: 'var(--text-tertiary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
              >
                ×
              </button>
            </div>

            <div
              className="p-4 rounded mb-4 min-h-[300px] max-h-[500px] overflow-y-auto geoint-scroll"
              style={{
                backgroundColor: 'var(--geoint-base)',
                border: 'var(--border-subtle)',
                fontFamily: 'var(--font-body)',
                color: 'var(--text-secondary)',
                lineHeight: '1.8',
                whiteSpace: 'pre-wrap',
              }}
            >
              {isGeneratingBrief ? (
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                  <span>Diplomatik özet hazırlanıyor...</span>
                </div>
              ) : (
                typewriterText
              )}
            </div>

            {!isGeneratingBrief && generatedBrief && (
              <div className="flex gap-2 justify-end">
                <button
                  onClick={copyBriefToClipboard}
                  className="flex items-center gap-2 px-4 py-2 text-sm rounded transition-colors"
                  style={{
                    backgroundColor: 'var(--geoint-elevated)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-label)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--signal-info)';
                    e.currentTarget.style.color = '#000';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--geoint-elevated)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }}
                >
                  <FileText className="w-4 h-4" />
                  Kopyala
                </button>
                <button
                  onClick={printAsPDF}
                  className="flex items-center gap-2 px-4 py-2 text-sm rounded transition-colors"
                  style={{
                    backgroundColor: 'var(--signal-info)',
                    color: '#000',
                    fontFamily: 'var(--font-label)',
                    fontWeight: 600,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--sentiment-partner)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--signal-info)';
                  }}
                >
                  <Printer className="w-4 h-4" />
                  PDF Olarak İndir
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Print Styles */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @media print {
          body {
            background: white !important;
            color: black !important;
          }
          .no-print {
            display: none !important;
          }
          canvas {
            max-width: 100% !important;
            page-break-inside: avoid;
          }
        }
      `,
        }}
      />
    </>
  );
};
