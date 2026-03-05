// service-worker.js - Version v7 (optimisée avec filtrage externe et cache intelligent)
const CACHE_NAME = 'mr-xpronos-v7';

// Activer les logs uniquement en développement
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

// Installation : mise en cache des statiques
self.addEventListener('install', event => {
  log('🔧 Installation Service Worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        log('📦 Mise en cache des fichiers statiques...');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activation : nettoyage des anciens caches
self.addEventListener('activate', event => {
  log('🚀 Activation Service Worker...');
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => {
          log('🗑️ Suppression ancien cache:', key);
          return caches.delete(key);
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Stratégie intelligente avec filtrage des requêtes externes
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Ignorer les requêtes vers d'autres domaines (API, images externes, etc.)
  if (url.origin !== location.origin) {
    log('🌐 Requête externe ignorée:', url.pathname);
    return;
  }

  // === JSON dynamiques : Network First ===
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
        .catch(() => {
          log('📴 Offline → utilisation du cache pour', url.pathname);
          return caches.match(event.request);
        })
    );
    return;
  }

  // === Pages HTML : Cache First, puis réseau, puis fallback offline ===
  if (event.request.destination === 'document' || url.pathname.endsWith('.html') || url.pathname === '/') {
    event.respondWith(
      caches.match(event.request)
        .then(cached => {
          if (cached) return cached;
          return fetch(event.request)
            .catch(() => {
              log('🌍 Fallback offline pour', url.pathname);
              return caches.match('/offline.html');
            });
        })
    );
    return;
  }

  // === Toutes les autres ressources (CSS, JS, images) : Cache First ===
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
  );
});

// Notification de mise à jour (optionnel)
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});