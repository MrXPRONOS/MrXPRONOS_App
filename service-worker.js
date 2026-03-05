// service-worker.js - Version avancée offline avec pronos
const CACHE_NAME = 'mr-xpronos-v6'; // Incrémente le numéro à chaque mise à jour majeure

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
    '/offline.html',           // Page offline personnalisée
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

// Installation : mise en cache des fichiers statiques
self.addEventListener('install', event => {
    console.log('🔧 Installation Service Worker...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('📦 Mise en cache des fichiers statiques...');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activation : nettoyage des anciens caches
self.addEventListener('activate', event => {
    console.log('🚀 Activation Service Worker...');
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Stratégie de cache intelligente
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // === Fichiers JSON dynamiques : Network First (toujours frais) ===
    if (DYNAMIC_JSON.some(file => url.pathname.endsWith(file))) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // Si la réponse est OK, on met à jour le cache
                    if (response && response.status === 200) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                    }
                    return response;
                })
                .catch(() => {
                    console.log(`📴 Offline → utilisation du cache pour ${url.pathname}`);
                    return caches.match(event.request);
                })
        );
        return;
    }

    // === Pages HTML : Cache First, puis réseau, puis fallback offline.html ===
    if (event.request.destination === 'document' || url.pathname.endsWith('.html') || url.pathname === '/') {
        event.respondWith(
            caches.match(event.request)
                .then(cached => {
                    if (cached) return cached; // Cache hit → direct
                    // Sinon on tente le réseau
                    return fetch(event.request)
                        .catch(() => caches.match('/offline.html')); // Fallback offline
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
                    // Mise en cache automatique des nouvelles ressources
                    if (response && response.status === 200) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                    }
                    return response;
                });
            })
    );
});