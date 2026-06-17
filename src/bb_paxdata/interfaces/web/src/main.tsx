/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';
import { useOfflineVerdictQueueSync } from '@/hooks/useOfflineVerdictQueueSync';
import { useQueueWebSocket } from '@/hooks/useQueueWebSocket';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: {
      retry: 0,
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
