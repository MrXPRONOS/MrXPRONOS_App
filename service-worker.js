// service-worker.js - Version v8 (optimisée avec cache intelligent)
const CACHE_NAME = 'mr-xpronos-v8';

const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';
const log = IS_DEV ? console.log : () => {};

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/pronos.html',
  '/historique.html',
  '/blog.html',
  '/conseils.html',
  '/infos.html',
  '/bonus.html',
  '/contact.html',
  '/article.html',
  '/offline.html',
  '/manifest.json',
  '/assets/css/style.css',
  '/assets/js/main.js',
  '/assets/js/pwa.js',
  '/assets/images/default-logo.png',
  '/assets/images/1xbet.png',
  '/assets/images/1win.png',
  '/assets/images/betwinner.png',
  '/assets/images/melbet.png',
  '/assets/images/linebet.png',
  '/assets/images/betclic.png',
  '/assets/images/whatsapp.png',
  '/assets/images/telegram.png',
  '/assets/images/instagram.png',
  '/assets/images/facebook.png',
  '/assets/images/youtube.png',
  '/assets/images/threads.png',
  '/assets/images/phone.png',
  '/assets/images/icon-192.png',
  '/assets/images/icon-512.png'
];

const DYNAMIC_JSON = [
  '/data.json',
  '/articles.json',
  '/conseils.json',
  '/footnews.json'
];

self.addEventListener('install', event => {
  log('🔧 Installation Service Worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  log('🚀 Activation Service Worker...');
  event.waitUntil(
    caches.keys().then(keys => 
      Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  // Stratégie : Network First pour les JSON, Cache First pour le reste
  if (DYNAMIC_JSON.some(file => url.pathname.endsWith(file))) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  if (event.request.destination === 'document' || url.pathname.endsWith('.html') || url.pathname === '/') {
    event.respondWith(
      caches.match(event.request)
        .then(cached => cached || fetch(event.request).catch(() => caches.match('/offline.html')))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(cached => cached || fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }))
  );
});

self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});