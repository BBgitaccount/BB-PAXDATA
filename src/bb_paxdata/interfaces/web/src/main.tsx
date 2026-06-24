/* eslint-disable react-refresh/only-export-components */
import { useOfflineVerdictQueueSync } from '@/hooks/useOfflineVerdictQueueSync';
import { useQueueWebSocket } from '@/hooks/useQueueWebSocket';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2, // 2 dk - stale-while-revalidate pattern
      gcTime: 1000 * 60 * 10, // 10 dk bellekte tut (eski adıyla cacheTime)
      retry: (failureCount, error) => {
        if ((error as { status?: number }).status && (error as { status?: number }).status! >= 500)
          return failureCount < 3;
        return false;
      },
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
      onError: (error) => {
        // Global error handling
        console.error('Mutation error:', error);
      },
    },
  },
});

const AppBootstrap = () => {
  useOfflineVerdictQueueSync();
  useQueueWebSocket();

  return <App />;
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppBootstrap />
    </QueryClientProvider>
  </React.StrictMode>,
);
