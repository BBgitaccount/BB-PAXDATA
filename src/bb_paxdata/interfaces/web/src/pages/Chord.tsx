import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ChordDiagram } from './WorldMap/components/ChordDiagram';

export const Chord = () => {
  return (
    <ErrorBoundary>
      <ChordDiagram />
    </ErrorBoundary>
  );
};
