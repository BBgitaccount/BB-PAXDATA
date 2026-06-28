import { useMutation, useQueryClient } from '@tanstack/react-query';
import { RotateCcw, Send } from 'lucide-react';
import { useState } from 'react';
import { useToast } from '@/hooks/useToast';
import { apiClient } from '@/services/apiClient';
import { enqueueVerdict, isOfflineCapableError } from '@/services/offlineVerdictQueue';
import { useReviewQueueStore } from '@/store/reviewQueueStore';
import type { ConfidenceLevel, HumanVerdict, VerdictPayload, VerdictResponse } from '@/types';
import { cn } from '@/utils/helpers';
import { ConfidenceSelector } from './ConfidenceSelector';

interface VerdictFormProps {
  logId: number;
  onSubmitted?: () => void;
}

type VerdictSubmissionResult = { mode: 'online'; response: VerdictResponse } | { mode: 'queued' };

export const VerdictForm = ({ logId, onSubmitted }: VerdictFormProps) => {
  const [verdict, setVerdict] = useState<HumanVerdict | null>(null);
  const [correctedValue, setCorrectedValue] = useState('');
  const [confidence, setConfidence] = useState<ConfidenceLevel | null>(null);
  const [justification, setJustification] = useState('');
  const [note, setNote] = useState('');
  const toast = useToast();
  const queryClient = useQueryClient();
  const applyOptimisticVerdict = useReviewQueueStore((state) => state.applyOptimisticVerdict);
  const rollbackOptimisticVerdict = useReviewQueueStore((state) => state.rollbackOptimisticVerdict);

  const submitVerdictMutation = useMutation({
    mutationFn: async (payload: VerdictPayload): Promise<VerdictSubmissionResult> => {
      try {
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
          throw new TypeError('Offline');
        }

        const response = await apiClient.post<VerdictResponse>('/api/v1/verdict', payload);
        return { mode: 'online', response };
      } catch (error) {
        if (isOfflineCapableError(error)) {
          await enqueueVerdict(payload);
          return { mode: 'queued' };
        }

        throw error;
      }
    },
    onMutate: async () => applyOptimisticVerdict(logId),
    onSuccess: (result) => {
      if (result.mode === 'queued') {
        toast.warning(
          'Çevrimdışı mod: karar yerel kuyruğa kaydedildi, bağlantı gelince gönderilecek.',
        );
      } else {
        void queryClient.invalidateQueries({ queryKey: ['fail-queue'] });
        void queryClient.invalidateQueries({
          queryKey: ['dashboard-overview'],
        });
        toast.success('Karar başarıyla kaydedildi.');
      }

      onSubmitted?.();
    },
    onError: (_error, _payload, context) => {
      if (context) {
        rollbackOptimisticVerdict(context);
      }

      toast.error('Karar kaydedilirken hata oluştu.');
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verdict || !confidence || justification.length < 10) {
      toast.error('Karar, güven seviyesi ve gerekçe (min 10 karakter) zorunludur.');
      return;
    }
    if (verdict === 'CORRECTED' && !correctedValue) {
      toast.error('Düzeltilmiş değer girilmelidir.');
      return;
    }

    const payload: VerdictPayload = {
      log_id: logId,
      verdict,
      corrected_value: verdict === 'CORRECTED' ? parseFloat(correctedValue) : null,
      note: note || null,
      confidence,
      justification,
      reviewer_id: 'current_user',
    };

    try {
      await submitVerdictMutation.mutateAsync(payload);
    } catch {
      return;
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label className="label-micro mb-3 block">Karar</label>
        <div className="grid grid-cols-3 gap-2">
          {(['CONFIRMED_FAIL', 'CONFIRMED_PASS', 'CORRECTED'] as HumanVerdict[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setVerdict(v)}
              className={cn(
                'py-3 text-xs font-medium tracking-diplomatic border transition-all duration-swift',
                verdict === v
                  ? 'bg-carbon-50 text-carbon-950 border-carbon-50'
                  : 'bg-transparent text-carbon-400 border-carbon-550 hover:border-carbon-400 hover:text-carbon-200',
              )}
            >
              {v === 'CONFIRMED_FAIL' && 'HATA ONAYLANDI'}
              {v === 'CONFIRMED_PASS' && 'YANLIŞ ALARM'}
              {v === 'CORRECTED' && 'DÜZELTİLDİ'}
            </button>
          ))}
        </div>
      </div>

      {verdict === 'CORRECTED' && (
        <div>
          <label className="label-micro mb-2 block">Düzeltilmiş Değer</label>
          <input
            type="number"
            step="0.001"
            value={correctedValue}
            onChange={(e) => setCorrectedValue(e.target.value)}
            className="w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 focus:border-carbon-300 font-mono"
            placeholder="0.000"
          />
        </div>
      )}

      <div>
        <label className="label-micro mb-3 block">Güven Seviyesi</label>
        <ConfidenceSelector value={confidence} onChange={setConfidence} />
      </div>

      <div>
        <label className="label-micro mb-2 block">
          Gerekçe <span className="text-carbon-500">(Zorunlu, min 10 karakter)</span>
        </label>
        <textarea
          value={justification}
          onChange={(e) => setJustification(e.target.value)}
          rows={4}
          className="w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 focus:border-carbon-300 resize-none"
          placeholder="Kararınızın gerekçesini detaylandırın..."
        />
        <div className="mt-1 text-right text-micro text-carbon-500 font-mono">
          {justification.length} / 10+ karakter
        </div>
      </div>

      <div>
        <label className="label-micro mb-2 block">
          Not <span className="text-carbon-500">(Opsiyonel)</span>
        </label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className="w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 focus:border-carbon-300 resize-none"
          placeholder="Ek notlar..."
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={submitVerdictMutation.isPending}
          className={cn(
            'flex-1 btn-primary py-3 flex items-center justify-center gap-2',
            submitVerdictMutation.isPending && 'opacity-50',
          )}
        >
          <Send className="w-3.5 h-3.5" strokeWidth={2} />
          {submitVerdictMutation.isPending ? 'İŞLENİYOR...' : 'KARARI GÖNDER'}
        </button>
        <button type="button" className="btn-secondary py-3 flex items-center gap-2">
          <RotateCcw className="w-3.5 h-3.5" strokeWidth={2} />
          GERİ AL
        </button>
      </div>
    </form>
  );
};
