import { ArrowRight, BookOpen, GitCompare, Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { DataTable } from '@/components/DataTable';
import { FrameSelector } from '@/components/FrameSelector';
import { GOLD_STANDARDS } from '@/constants/goldStandards';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { mockApi } from '@/services/mockApi';
import type { AgreementStatus, HumanReviewEntry } from '@/types';
import { cn } from '@/utils/helpers';

export const AIComparison = () => {
  const [entries, setEntries] = useState<HumanReviewEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEntry, setSelectedEntry] = useState<HumanReviewEntry | null>(null);
  const toast = useToast();
  const { t } = useTranslation();
  const goldStandards = GOLD_STANDARDS;

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    try {
      const e = await mockApi.getHumanReviews();
      setEntries(e);
    } catch {
      toast.error('Veriler yüklenemedi.');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    toast.success('İnsan düzeltmesi kaydedildi.');
    setSelectedEntry(null);
  };

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
          {t('comparison.title')}
        </h1>
        <p className="text-sm text-carbon-400 mt-1">{t('comparison.desc')}</p>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-7">
          <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
            <div className="flex items-center gap-2 mb-6">
              <GitCompare className="w-4 h-4 text-carbon-400" />
              <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                İnceleme Listesi
              </h2>
            </div>
            <DataTable
              columns={[
                {
                  key: 'id',
                  header: 'ID',
                  width: '60px',
                  render: (r) => <span className="font-mono text-2xs text-carbon-300">{r.id}</span>,
                },
                {
                  key: 'text',
                  header: 'Cümle',
                  render: (r) => (
                    <span className="text-sm text-carbon-200">
                      {r.sentence_text.slice(0, 80)}...
                    </span>
                  ),
                },
                {
                  key: 'ai_frame',
                  header: 'AI Frame',
                  width: '120px',
                  render: (r) => (
                    <span className="font-mono text-micro text-carbon-300">
                      {r.ai_dominant_frame}
                    </span>
                  ),
                },
                {
                  key: 'ai_risk',
                  header: 'AI Risk',
                  width: '80px',
                  render: (r) => (
                    <span className="font-mono text-micro text-carbon-300">{r.ai_risk_level}</span>
                  ),
                },
                {
                  key: 'status',
                  header: 'Durum',
                  width: '100px',
                  render: (r) => (
                    <span
                      className={cn(
                        'text-micro font-mono',
                        r.agreement_status ? 'text-carbon-300' : 'text-carbon-500',
                      )}
                    >
                      {r.agreement_status || 'BEKLEMEDE'}
                    </span>
                  ),
                },
                {
                  key: 'action',
                  header: '',
                  width: '80px',
                  render: (r) => (
                    <button
                      onClick={() => setSelectedEntry(r)}
                      className="flex items-center gap-1 px-2 py-1 bg-carbon-800 text-carbon-200 text-micro hover:bg-carbon-700 transition-colors"
                    >
                      <ArrowRight className="w-3 h-3" />
                      İNCELE
                    </button>
                  ),
                },
              ]}
              data={entries}
              keyExtractor={(r) => r.id}
              loading={loading}
            />
          </div>
        </div>

        <div className="col-span-5">
          {selectedEntry ? (
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-6">
              <div className="flex items-center gap-2 mb-2">
                <GitCompare className="w-4 h-4 text-carbon-400" />
                <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
                  İnceleme Formu
                </h2>
              </div>

              <div className="p-4 bg-carbon-800/50 border border-hair border-carbon-550">
                <span className="label-micro mb-2 block">Cümle</span>
                <p className="text-sm text-carbon-200 leading-relaxed">
                  {selectedEntry.sentence_text}
                </p>
              </div>

              <div className="space-y-3">
                <span className="label-micro block">AI Çıktıları (Referans)</span>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-carbon-800/30 border border-hair border-carbon-550">
                    <span className="text-micro text-carbon-500 block">SBI Score</span>
                    <span className="text-sm font-mono text-carbon-300">
                      {selectedEntry.ai_sbi_score}
                    </span>
                  </div>
                  <div className="p-3 bg-carbon-800/30 border border-hair border-carbon-550">
                    <span className="text-micro text-carbon-500 block">Dominant Frame</span>
                    <span className="text-sm font-mono text-carbon-300">
                      {selectedEntry.ai_dominant_frame}
                    </span>
                  </div>
                  <div className="p-3 bg-carbon-800/30 border border-hair border-carbon-550">
                    <span className="text-micro text-carbon-500 block">Risk Level</span>
                    <span className="text-sm font-mono text-carbon-300">
                      {selectedEntry.ai_risk_level}
                    </span>
                  </div>
                  <div className="p-3 bg-carbon-800/30 border border-hair border-carbon-550">
                    <span className="text-micro text-carbon-500 block">Sentiment</span>
                    <span className="text-sm font-mono text-carbon-300">
                      {selectedEntry.ai_sentiment_score}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <span className="label-micro block">İnsan Düzeltmeleri</span>
                <div>
                  <label className="text-micro text-carbon-400 mb-1 block">
                    SBI Score [-100, 100]
                  </label>
                  <input type="range" min={-100} max={100} step={0.1} className="w-full" />
                </div>
                <div>
                  <label className="text-micro text-carbon-400 mb-1 block">Dominant Frame</label>
                  <FrameSelector value={selectedEntry.human_dominant_frame} onChange={() => {}} />
                </div>
                <div>
                  <label className="text-micro text-carbon-400 mb-1 block">Risk Level</label>
                  <select className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550">
                    <option>LOW</option>
                    <option>MED</option>
                    <option>HIGH</option>
                    <option>CRITICAL</option>
                  </select>
                </div>
                <div>
                  <label className="text-micro text-carbon-400 mb-1 block">
                    Sentiment [-1.0, 1.0]
                  </label>
                  <input type="range" min={-1} max={1} step={0.01} className="w-full" />
                </div>
              </div>

              <div className="space-y-3">
                <span className="label-micro block">Anlaşma Durumu</span>
                <div className="grid grid-cols-4 gap-2">
                  {(['AGREED', 'PARTIAL', 'DISAGREED', 'ESCALATED'] as AgreementStatus[]).map(
                    (a) => (
                      <button
                        key={a}
                        className="py-2 text-micro font-medium tracking-diplomatic border border-carbon-550 text-carbon-400 hover:border-carbon-400 hover:text-carbon-200 transition-colors"
                      >
                        {a}
                      </button>
                    ),
                  )}
                </div>
              </div>

              <div>
                <label className="text-micro text-carbon-400 mb-1 block">
                  Anlaşmazlık Gerekçesi
                </label>
                <textarea
                  rows={3}
                  className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550 resize-none"
                  placeholder="Max 2000 karakter..."
                />
              </div>

              <button
                onClick={handleSave}
                className="w-full btn-primary py-3 flex items-center justify-center gap-2"
              >
                <Save className="w-3.5 h-3.5" />
                KAYDET
              </button>
            </div>
          ) : (
            <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 h-full flex items-center justify-center">
              <p className="text-sm text-carbon-400">İncelemek için bir kayıt seçin</p>
            </div>
          )}
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <BookOpen className="w-4 h-4 text-carbon-400" />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Gold Standard Örnekler
          </h2>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {goldStandards.map((ex, i) => (
            <div key={i} className="p-4 border border-hair border-carbon-550 bg-carbon-800/30">
              <span className="font-mono text-micro text-carbon-300 block mb-2">
                {ex.frame_type}
              </span>
              <p className="text-sm text-carbon-200 leading-relaxed mb-3">{ex.sentence_text}</p>
              <p className="text-2xs text-carbon-500">{ex.explanation}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
