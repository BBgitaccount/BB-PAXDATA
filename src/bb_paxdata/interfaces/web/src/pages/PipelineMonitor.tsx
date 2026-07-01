import { ExternalLink, Play, RefreshCw, Server, Zap } from 'lucide-react';
import { useState } from 'react';
import { BuildTUIMonitor } from '@/components/BuildTUIMonitor';
import { useToast } from '@/hooks/useToast';
import { useTranslation } from '@/hooks/useTranslation';
import { apiClient } from '@/services/apiClient';

export const PipelineMonitor = () => {
  const toast = useToast();
  const { t } = useTranslation();
  const [isStarting, setIsStarting] = useState(false);

  const handleStartPipeline = async () => {
    try {
      setIsStarting(true);
      await apiClient.post('/api/v1/pipeline/start', {});
      toast.success(
        'Pipeline Docker üzerinde başlatıldı. İlerlemeyi terminalden takip edebilirsiniz.',
      );
    } catch (error) {
      toast.error('Pipeline başlatılırken bir hata oluştu');
    } finally {
      setIsStarting(false);
    }
  };

  const handleRefresh = () => {
    toast.info('Giriş veri akış bağlantısı yenileniyor...');
  };

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('monitor.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('monitor.desc')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleStartPipeline}
            disabled={isStarting}
            className="btn-primary flex items-center gap-2 px-4 py-1.5 text-xs disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            {isStarting ? 'BAŞLATILIYOR...' : "PİPELINE'I BAŞLAT"}
          </button>
          <button
            type="button"
            onClick={handleRefresh}
            className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-xs border-carbon-600 hover:bg-carbon-800"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Yenile
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Terminal Widget */}
        <div className="lg:col-span-2 space-y-4">
          <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-carbon-400" />
                <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                  Canlı Akış Terminali
                </h3>
              </div>
            </div>

            {/* Mount existing websocket monitor */}
            <BuildTUIMonitor />
          </div>
        </div>

        {/* Worker Info & Grafana Link */}
        <div className="lg:col-span-1 space-y-6">
          <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-6">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-carbon-400" />
              <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
                Worker & Task Durumu
              </h3>
            </div>

            <div className="space-y-4">
              <p className="text-xs text-carbon-400 leading-relaxed">
                İşlemler Celery worker kuyruğu üzerinden asenkron yönetilmektedir. Detaylı CPU,
                kuyruk bekleme süreleri ve task throughput analizi için Grafana worker izleme
                panelini kullanabilirsiniz.
              </p>

              <div className="border border-hair border-carbon-850 p-4 bg-carbon-950/40 rounded space-y-3 font-mono text-2xs">
                <div className="flex justify-between">
                  <span className="text-carbon-450">Celery Exporter</span>
                  <span className="text-signal-pass font-semibold">ONLINE (8888)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-450">Active Workers</span>
                  <span className="text-carbon-100 font-tabular font-semibold">2 (cpu, io)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-carbon-450">Broker Backend</span>
                  <span className="text-carbon-100 font-semibold">Redis (6379)</span>
                </div>
              </div>

              <a
                href="http://localhost:3000/d/bbpaxdata-celery-workers/celery-workers?orgId=1"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 text-2xs font-medium tracking-diplomatic text-carbon-950 bg-carbon-50 hover:bg-carbon-200 transition-colors uppercase rounded"
              >
                CELERY WORKERS DETAYINA GİT
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Embedded Workers Dashboard at bottom */}
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-carbon-400" />
          <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
            Worker İşlem Dağılım Grafiği
          </h3>
        </div>
        <div className="relative aspect-[21/9] w-full bg-[var(--bg-primary)] border border-hair overflow-hidden rounded-none">
          <iframe
            src="http://localhost:3000/d/bbpaxdata-celery-workers/celery-workers?orgId=1&kiosk=tv&theme=dark"
            width="100%"
            height="100%"
            frameBorder="0"
            title="Celery Workers"
            className="absolute inset-0 w-full h-full"
            allowFullScreen
          />
        </div>
      </div>
    </div>
  );
};
