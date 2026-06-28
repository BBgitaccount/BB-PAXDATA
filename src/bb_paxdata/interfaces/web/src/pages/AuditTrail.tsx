import { CheckCircle, FileSearch } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AuditTrailTable } from '@/components/AuditTrailTable';
import { StatusBadge } from '@/components/StatusBadge';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { apiClient } from '@/services/apiClient';
import type { AuditEntry } from '@/types';

export const AuditTrail = () => {
  const [data, setData] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [secondEye, setSecondEye] = useState<AuditEntry[]>([]);
  const toast = useToast();
  const { hasPermission } = useAuth();
  const { t } = useTranslation();

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const all = await apiClient.get<AuditEntry[]>('/api/v1/verdict/audit?limit=50');
      setData(all);
      setSecondEye(all.filter((a) => a.review_status === 'PENDING'));
    } catch {
      toast.error('Denetim izi yüklenemedi.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = (auditId: number) => {
    toast.success(`Audit #${auditId} onaylandı.`);
    setSecondEye((prev) => prev.filter((s) => s.audit_id !== auditId));
  };

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-carbon-50">{t('audit.title')}</h1>
        <p className="text-sm text-carbon-400 mt-1">{t('audit.desc')}</p>
      </div>

      {hasPermission('escalate') && secondEye.length > 0 && (
        <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileSearch className="w-4 h-4 text-carbon-400" />
            <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
              İkinci Göz Bekleyenler
            </h2>
            <span className="ml-2 px-2 py-0.5 bg-carbon-50 text-carbon-950 text-micro font-mono">
              {secondEye.length}
            </span>
          </div>
          <div className="space-y-2">
            {secondEye.map((item) => (
              <div
                key={item.audit_id}
                className="flex items-center justify-between py-3 border-b border-hair border-carbon-550/50"
              >
                <div className="flex items-center gap-4">
                  <span className="font-mono text-2xs text-carbon-300">#{item.audit_id}</span>
                  <span className="text-2xs text-carbon-400">{item.performed_by}</span>
                  <StatusBadge status={item.action_type} />
                  <span className="text-2xs text-carbon-400 max-w-md truncate">
                    {item.justification}
                  </span>
                </div>
                <button
                  onClick={() => handleApprove(item.audit_id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-carbon-50 text-carbon-950 text-micro font-medium tracking-diplomatic hover:bg-carbon-200 transition-colors"
                >
                  <CheckCircle className="w-3 h-3" />
                  ONAYLA
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <FileSearch className="w-4 h-4 text-carbon-400" />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Tam Denetim Geçmişi
          </h2>
        </div>
        <AuditTrailTable data={data} loading={loading} />
      </div>
    </div>
  );
};
