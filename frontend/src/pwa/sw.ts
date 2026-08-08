/**
 * Progressive Web App (PWA) Service Worker for Project Loot Raiders.
 * Provides offline shell caching and network-first deal API fallbacks.
 */

const CACHE_NAME = 'loot-raiders-v2';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/admin.html',
  '/manifest.json'
];

self.addEventListener('install', (event: any) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('fetch', (event: any) => {
  const url = new URL(event.request.url);

  // Network-first for API routes, Cache-first for static assets
  if (url.pathname.startsWith('/api')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  } else {
    event.respondWith(
      caches.match(event.request).then((response) => response || fetch(event.request))
    );
  }
});
