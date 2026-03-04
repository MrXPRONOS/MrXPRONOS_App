/**
 * service-worker.js - Gère le cache et les requêtes réseau pour la PWA
 * Stratégie : cache-first pour les assets statiques, réseau pour data.json
 */

const CACHE_NAME = 'mr-xpronos-v1';
const urlsToCache = [
    '/',
    '/index.html',
    '/pronos.html',
    '/historique.html',
    '/blog.html',
    '/conseils.html',
    '/infos.html',
    '/contact.html',
    '/article.html',
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
    '/assets/images/888starz.png',
    '/assets/images/whatsapp.png',
    '/assets/images/telegram.png',
    '/assets/images/instagram.png',
    '/assets/images/facebook.png',
    '/assets/images/youtube.png',
    '/assets/images/phone.png'
];

// Installation : mise en cache des fichiers statiques
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Mise en cache des ressources statiques');
                return cache.addAll(urlsToCache);
            })
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

// Interception des requêtes : stratégie cache-first pour les statiques, réseau pour data.json
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Pour data.json, toujours passer par le réseau (pour avoir les scores à jour)
    if (url.pathname.endsWith('/data.json')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // Mettre en cache la nouvelle version
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                    return response;
                })
                .catch(() => {
                    // Si réseau indisponible, essayer le cache
                    return caches.match(event.request);
                })
        );
        return;
    }

    // Pour les autres ressources (CSS, JS, images, HTML), on utilise cache-first
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response; // retourne la version en cache
                }
                // Sinon, on va chercher sur le réseau
                return fetch(event.request).then(networkResponse => {
                    // Mettre en cache la nouvelle ressource
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                    return networkResponse;
                });
            })
    );
});