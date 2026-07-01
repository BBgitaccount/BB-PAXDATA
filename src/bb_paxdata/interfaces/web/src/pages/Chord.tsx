import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Globe } from 'lucide-react';
import { ChordDiagram } from './WorldMap/components/ChordDiagram';

export const Chord = () => {
  return (
    <ErrorBoundary>
      <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
              <Globe className="w-6 h-6 text-[var(--text-secondary)]" />
              Chord Diyagramı
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-2 max-w-3xl">
              Ülkeler arasındaki diplomatik ilişki akışlarını gösteren dairesel görselleştirme.
            </p>
          </div>
        </div>

        {/* Chord Diagram */}
        <ChordDiagram />
      </div>
    </ErrorBoundary>
  );
};
