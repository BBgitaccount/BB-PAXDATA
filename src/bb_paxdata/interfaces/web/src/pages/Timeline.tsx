import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Globe } from 'lucide-react';
import { SessionTimelinePanel } from './WorldMap/components/SessionTimelinePanel';

export const Timeline = () => {
  return (
    <ErrorBoundary>
      <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
              <Globe className="w-6 h-6 text-[var(--text-secondary)]" />
              Oturum Zaman Çizelgesi
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-2 max-w-3xl">
              Diplomatik oturumların zaman içindeki değişimlerini gösteren analiz paneli.
            </p>
          </div>
        </div>

        {/* Timeline Panel */}
        <SessionTimelinePanel />
      </div>
    </ErrorBoundary>
  );
};
