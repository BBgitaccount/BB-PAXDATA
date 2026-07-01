import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Globe } from 'lucide-react';
import { SankeyFlowDiagram } from './WorldMap/components/SankeyFlowDiagram';

export const Sankey = () => {
  return (
    <ErrorBoundary>
      <div className="space-y-6 animate-[fade-in-up_300ms_ease-out_both]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
              <Globe className="w-6 h-6 text-[var(--text-secondary)]" />
              Sankey Akış Diyagramı
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-2 max-w-3xl">
              Diplomatik referans bağlamlarını gösteren akış görselleştirmesi.
            </p>
          </div>
        </div>

        {/* Sankey Diagram */}
        <SankeyFlowDiagram />
      </div>
    </ErrorBoundary>
  );
};
