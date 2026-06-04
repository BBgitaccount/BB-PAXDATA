/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { BackgroundSyncPlugin } from 'workbox-background-sync';

declare const self: ServiceWorkerGlobalScope;

// Precache static assets compiled by build tools (Vite/Webpack)
precacheAndRoute(self.__WB_MANIFEST || []);

// 1. Queue Endpoint API Requests - NetworkFirst
// Ensure reviewers get fresh queue items when online, fall back to cached queue offline.
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/queue/'),
  new NetworkFirst({
    cacheName: 'api-queue-cache',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 24 * 3600, // 24 Hours
      }),
    ],
  })
);

// 2. Static Assets (Google Fonts, styling, scripts) - CacheFirst
registerRoute(
  ({ request }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'worker' ||
    request.destination === 'font',
  new CacheFirst({
    cacheName: 'static-resources',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 30 * 24 * 3600, // 30 Days
      }),
    ],
  })
);

// 3. Background Sync for Verdict Submissions
// Automatically re-tries posting verdicts when connection is restored.
const bgSyncPlugin = new BackgroundSyncPlugin('verdict-sync-queue', {
  maxRetentionTime: 24 * 60, // Retry for up to 24 hours (in minutes)
});

registerRoute(
  ({ url }) => url.pathname.endsWith('/submit-verdict') || url.pathname.includes('/api/v1/verdict/'),
  new NetworkFirst({
    cacheName: 'api-verdicts-cache',
    plugins: [bgSyncPlugin],
  }),
  'POST'
);

// Lifecycle management
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});
