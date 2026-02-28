/**
 * service-worker.js - Met en cache les ressources pour un fonctionnement hors ligne
 * Stratégie : cache-first pour les fichiers statiques, réseau pour le reste.
 * Chemins relatifs pour GitHub Pages.
 */

const CACHE_NAME = 'mr-xpronos-v1';
const urlsToCache = [
    'index.html',
    'pronos.html',
    'blog.html',
    'conseils.html',
    'infos.html',
    'article.html',
    'admin.html',
    'contact.html',
    'assets/css/style.css',
    'assets/js/main.js',
    'assets/js/pwa.js',
    'assets/js/admin-stats.js',
    'manifest.json',
    'data.json'
];

// Installation : mise en cache des fichiers essentiels
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

// Interception des requêtes : réponse depuis le cache si disponible, sinon réseau
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => response || fetch(event.request))
    );
});

// Activation : nettoyage des anciens caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        })
    );
});
