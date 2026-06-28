import {
  Key,
  RotateCcw,
  Save,
  Settings as SettingsIcon,
  Terminal,
  ToggleLeft,
  ToggleRight,
  Users,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { BuildTUIMonitor } from '@/components/BuildTUIMonitor';
import { RangeSlider } from '@/components/RangeSlider';
import { ReviewerTable } from '@/components/ReviewerTable';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { ApiError, apiClient } from '@/services/apiClient';
import type { Reviewer, SystemSettings } from '@/types';

export const Settings = () => {
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newReviewer, setNewReviewer] = useState({
    reviewer_id: '',
    scope_type: 'global',
    scope_value: '*',
    permission_level: 'view',
    max_daily_reviews: 50,
  });
  const toast = useToast();
  const { hasPermission } = useAuth();
  const { t } = useTranslation();

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async () => {
    try {
      const [r, s] = await Promise.all([
        apiClient.get<Reviewer[]>('/api/v1/settings/reviewers'),
        apiClient.get<SystemSettings>('/api/v1/settings/system'),
      ]);
      setReviewers(r);
      setSystemSettings(s);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          toast.error('Oturum süresi dolmuş, lütfen yeniden giriş yapın.');
        } else if (err.status === 403) {
          toast.error('Bu bölüme erişim yetkiniz yok.');
        } else {
          toast.error('Sunucu hatası: Ayarlar yüklenemedi.');
        }
      } else {
        toast.error('Ayarlar yüklenemedi.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = (reviewer: Reviewer) => {
    setReviewers((prev) =>
      prev.map((r) =>
        r.reviewer_id === reviewer.reviewer_id ? { ...r, is_active: !r.is_active } : r,
      ),
    );
    toast.success(`${reviewer.reviewer_id} ${reviewer.is_active ? 'pasif' : 'aktif'} yapıldı.`);
  };

  const handleAddReviewer = () => {
    if (!newReviewer.reviewer_id) {
      toast.error('Reviewer ID gereklidir.');
      return;
    }
    const reviewer: Reviewer = {
      ...newReviewer,
      current_daily_count: 0,
      is_active: true,
      created_at: new Date().toISOString(),
    } as Reviewer;
    setReviewers((prev) => [reviewer, ...prev]);
    setShowAddForm(false);
    setNewReviewer({
      reviewer_id: '',
      scope_type: 'global',
      scope_value: '*',
      permission_level: 'view',
      max_daily_reviews: 50,
    });
    toast.success('Reviewer eklendi.');
  };

  const handleResetDaily = () => {
    setReviewers((prev) => prev.map((r) => ({ ...r, current_daily_count: 0 })));
    toast.success('Günlük sayaçlar sıfırlandı.');
  };

  if (!hasPermission('admin')) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <SettingsIcon className="w-8 h-8 text-carbon-500 mx-auto mb-4" />
          <p className="text-sm text-carbon-400">{t('settings.no_permission')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
          {t('settings.title')}
        </h1>
        <p className="text-sm text-carbon-400 mt-1">{t('settings.desc')}</p>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-carbon-400" />
            <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Reviewer Yönetimi
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleResetDaily} className="btn-secondary flex items-center gap-2">
              <RotateCcw className="w-3.5 h-3.5" />
              SIFIRLA
            </button>
            <button onClick={() => setShowAddForm(!showAddForm)} className="btn-primary">
              + YENİ REVIEWER
            </button>
          </div>
        </div>

        {showAddForm && (
          <div className="mb-6 p-4 border border-hair border-carbon-550 bg-carbon-800/50">
            <div className="grid grid-cols-5 gap-4">
              <div>
                <label className="label-micro mb-2 block">Reviewer ID</label>
                <input
                  type="email"
                  value={newReviewer.reviewer_id}
                  onChange={(e) =>
                    setNewReviewer({
                      ...newReviewer,
                      reviewer_id: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550"
                  placeholder="email@paxdata.int"
                />
              </div>
              <div>
                <label className="label-micro mb-2 block">Scope Type</label>
                <select
                  value={newReviewer.scope_type}
                  onChange={(e) =>
                    setNewReviewer({
                      ...newReviewer,
                      scope_type: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550"
                >
                  <option value="formula">formula</option>
                  <option value="speaker">speaker</option>
                  <option value="panel">panel</option>
                  <option value="country">country</option>
                  <option value="global">global</option>
                </select>
              </div>
              <div>
                <label className="label-micro mb-2 block">Scope Value</label>
                <input
                  type="text"
                  value={newReviewer.scope_value}
                  onChange={(e) =>
                    setNewReviewer({
                      ...newReviewer,
                      scope_value: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550"
                />
              </div>
              <div>
                <label className="label-micro mb-2 block">Yetki</label>
                <select
                  value={newReviewer.permission_level}
                  onChange={(e) =>
                    setNewReviewer({
                      ...newReviewer,
                      permission_level: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550"
                >
                  <option value="view">view</option>
                  <option value="verdict">verdict</option>
                  <option value="correct">correct</option>
                  <option value="escalate">escalate</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <div>
                <label className="label-micro mb-2 block">Günlük Limit</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={newReviewer.max_daily_reviews}
                    onChange={(e) =>
                      setNewReviewer({
                        ...newReviewer,
                        max_daily_reviews: Number(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550"
                  />
                  <button onClick={handleAddReviewer} className="btn-primary px-4">
                    <Save className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <ReviewerTable data={reviewers} loading={loading} onToggleActive={handleToggleActive} />
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <SettingsIcon className="w-4 h-4 text-carbon-400" />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Sistem Parametreleri
          </h2>
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-hair border-carbon-550/50">
              <div>
                <span className="text-sm text-carbon-200">Anomaly Soft Log Only</span>
                <p className="text-2xs text-carbon-500">SOFT_ANOMALY'leri sadece logla</p>
              </div>
              <button
                onClick={() =>
                  setSystemSettings((prev) =>
                    prev
                      ? {
                          ...prev,
                          anomaly_soft_log_only: !prev.anomaly_soft_log_only,
                        }
                      : prev,
                  )
                }
                className="text-carbon-400 hover:text-carbon-50"
              >
                {systemSettings?.anomaly_soft_log_only ? (
                  <ToggleRight className="w-5 h-5" />
                ) : (
                  <ToggleLeft className="w-5 h-5" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-hair border-carbon-550/50">
              <div>
                <span className="text-sm text-carbon-200">Anomaly Controller</span>
                <p className="text-2xs text-carbon-500">Anomali kontrolcüsü aktif</p>
              </div>
              <button
                onClick={() =>
                  setSystemSettings((prev) =>
                    prev
                      ? {
                          ...prev,
                          anomaly_controller_enabled: !prev.anomaly_controller_enabled,
                        }
                      : prev,
                  )
                }
                className="text-carbon-400 hover:text-carbon-50"
              >
                {systemSettings?.anomaly_controller_enabled ? (
                  <ToggleRight className="w-5 h-5" />
                ) : (
                  <ToggleLeft className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
          <div className="space-y-4">
            <RangeSlider
              label="Context Window"
              min={1}
              max={20}
              value={systemSettings?.anomaly_context_window || 5}
              onChange={(val) =>
                setSystemSettings((prev) =>
                  prev ? { ...prev, anomaly_context_window: val } : prev,
                )
              }
            />
            <RangeSlider
              label="Risk AI Weight"
              min={0}
              max={1}
              step={0.1}
              value={systemSettings?.risk_ai_weight ?? 0.6}
              onChange={(val) =>
                setSystemSettings((prev) => (prev ? { ...prev, risk_ai_weight: val } : prev))
              }
            />
            <RangeSlider
              label="Risk Uyarı Eşik Değeri"
              min={0}
              max={100}
              step={5}
              value={systemSettings?.risk_threshold ?? 70}
              displayValue={`${systemSettings?.risk_threshold ?? 70}%`}
              onChange={(val) =>
                setSystemSettings((prev) => (prev ? { ...prev, risk_threshold: val } : prev))
              }
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <button
            onClick={async () => {
              if (systemSettings) {
                try {
                  await apiClient.put('/api/v1/settings/system', systemSettings);
                  toast.success(t('settings.save_toast'));
                } catch (err) {
                  if (err instanceof ApiError && err.status === 403) {
                    toast.error('Bu işlemi yapma yetkiniz yok.');
                  } else {
                    toast.error(t('common.error'));
                  }
                }
              }
            }}
            className="btn-primary flex items-center gap-2"
          >
            <Save className="w-3.5 h-3.5" strokeWidth={2.5} />
            PARAMETRELERİ KAYDET
          </button>
        </div>
      </div>

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <Key className="w-4 h-4 text-carbon-400" />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
            JWT Token Yönetimi
          </h2>
        </div>
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="reviewer_id"
            className="px-3 py-2 text-xs bg-carbon-900 border border-hair border-carbon-550 w-48"
          />
          <button className="btn-primary">TOKEN OLUŞTUR</button>
        </div>
      </div>

      {/* ── Pipeline Build Monitor ──────────────────────────────────────── */}
      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6">
        <div className="flex items-center gap-2 mb-6">
          <Terminal className="w-4 h-4 text-carbon-400" />
          <h2 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Pipeline Build Monitor
          </h2>
          <span className="ml-auto text-micro font-mono text-carbon-500">
            WebSocket — /api/ws/build
          </span>
        </div>
        <BuildTUIMonitor />
      </div>
    </div>
  );
};
