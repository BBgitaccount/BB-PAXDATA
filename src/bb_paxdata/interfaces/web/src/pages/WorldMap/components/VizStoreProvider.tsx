// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/VizStoreProvider.tsx

import { useEffect } from 'react';
import { useVizStore } from '../../../store/vizStore';

interface VizStoreProviderProps {
  children: React.ReactNode;
}

export const VizStoreProvider: React.FC<VizStoreProviderProps> = ({ children }) => {
  const fetchAllData = useVizStore((state) => state.fetchAllData);
  const loading = useVizStore((state) => state.loading.fetchAll);
  const error = useVizStore((state) => state.errors.fetchAll);

  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center h-screen"
        style={{ backgroundColor: 'var(--geoint-void)' }}
      >
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: 'var(--signal-info)', borderTopColor: 'transparent' }}
          />
          <span
            className="text-sm"
            style={{ fontFamily: 'var(--font-label)', color: 'var(--text-tertiary)' }}
          >
            Veriler yükleniyor...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex items-center justify-center h-screen p-6"
        style={{ backgroundColor: 'var(--geoint-void)' }}
      >
        <div className="max-w-md text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h3
            className="text-lg font-semibold mb-2"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}
          >
            Veri Yükleme Hatası
          </h3>
          <p
            className="text-sm mb-4"
            style={{ fontFamily: 'var(--font-body)', color: 'var(--text-secondary)' }}
          >
            {error}
          </p>
          <button
            onClick={fetchAllData}
            className="px-4 py-2 text-sm rounded transition-colors"
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
            Tekrar Dene
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
