// service-worker.js - Version v9 (optimisée avec stratégies avancées)
const CACHE_NAME = 'mr-xpronos-v9';
const STATIC_CACHE = 'mr-xpronos-static-v9';
const DYNAMIC_CACHE = 'mr-xpronos-dynamic-v9';
const IMAGE_CACHE = 'mr-xpronos-images-v9';

const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';
const log = IS_DEV ? console.log.bind(console) : () => {};

// Assets statiques à pré-cacher
const STATIC_ASSETS = [
    './',
    './index.html',
    './pronos.html',
    './historique.html',
    './blog.html',
    './conseils.html',
    './infos.html',
    './bonus.html',
    './contact.html',
    './article.html',
    './offline.html',
    './manifest.json',
    './assets/css/style.css',
    './assets/js/main.js',
    './assets/js/pwa.js',
    './assets/images/default-logo.png',
    './assets/images/1xbet.png',
    './assets/images/1win.png',
    './assets/images/betwinner.png',
    './assets/images/melbet.png',
    './assets/images/linebet.png',
    './assets/images/betclic.png',
    './assets/images/whatsapp.png',
    './assets/images/telegram.png',
    './assets/images/instagram.png',
    './assets/images/facebook.png',
    './assets/images/youtube.png',
    './assets/images/threads.png',
    './assets/images/phone.png',
    './assets/images/icon-72x72.png',
    './assets/images/icon-96x96.png',
    './assets/images/icon-128x128.png',
    './assets/images/icon-144x144.png',
    './assets/images/icon-192x192.png',
    './assets/images/icon-512x512.png'
];

// Fichiers JSON dynamiques
const DYNAMIC_JSON = [
    './data.json',
    './articles.json',
    './conseils.json',
    './footnews.json',
    './testimonials.json'
];

// Installation
self.addEventListener('install', (event) => {
    log('🔧 Installation Service Worker v9...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                log('📦 Mise en cache des assets statiques...');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                log('✅ Installation terminée');
                return self.skipWaiting();
            })
            .catch((err) => {
                log('❌ Erreur installation:', err);
            })
    );
});

// Activation et nettoyage des anciens caches
self.addEventListener('activate', (event) => {
    log('🚀 Activation Service Worker v9...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            return name.startsWith('mr-xpronos-') && 
                                   !name.includes('v9');
                        })
                        .map((name) => {
                            log('🗑️ Suppression ancien cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                log('✅ Activation terminée');
                return self.clients.claim();
            })
    );
});

// Stratégies de cache
const strategies = {
    // Cache First pour les assets statiques
    cacheFirst: async (request) => {
        const cache = await caches.open(STATIC_CACHE);
        const cached = await cache.match(request);
        
        if (cached) {
            // Rafraîchir en arrière-plan
            fetch(request).then((response) => {
                if (response && response.status === 200) {
                    cache.put(request, response.clone());
                }
            }).catch(() => {});
            
            return cached;
        }
        
        try {
            const response = await fetch(request);
            if (response && response.status === 200) {
                cache.put(request, response.clone());
            }
            return response;
        } catch (error) {
            return new Response('Offline', { status: 503 });
        }
    },
    
    // Network First pour les JSON (données fraîches prioritaires)
    networkFirst: async (request) => {
        const cache = await caches.open(DYNAMIC_CACHE);
        
        try {
            const networkResponse = await fetch(request);
            if (networkResponse && networkResponse.status === 200) {
                cache.put(request, networkResponse.clone());
                return networkResponse;
            }
        } catch (error) {
            log('📴 Hors ligne, utilisation du cache:', request.url);
        }
        
        const cached = await cache.match(request);
        if (cached) {
            return cached;
        }
        
        // Fallback pour data.json
        if (request.url.includes('data.json')) {
            return new Response(
                JSON.stringify({ 
                    matches: [], 
                    categories: { simple: [], pro: [], vip: [] },
                    stats: { total_bets: 0, wins: 0, roi: 0 },
                    bookmakers: []
                }),
                { headers: { 'Content-Type': 'application/json' } }
            );
        }
        
        return new Response('Offline', { status: 503 });
    },
    
    // Stale While Revalidate pour les images
    staleWhileRevalidate: async (request) => {
        const cache = await caches.open(IMAGE_CACHE);
        const cached = await cache.match(request);
        
        const fetchPromise = fetch(request).then((response) => {
            if (response && response.status === 200) {
                cache.put(request, response.clone());
            }
            return response;
        }).catch(() => cached);
        
        return cached || fetchPromise;
    }
};

// Gestion des requêtes
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Ignorer les requêtes non-GET
    if (request.method !== 'GET') return;
    
    // Ignorer les requêtes externes
    if (url.origin !== self.location.origin) return;
    
    // Stratégie selon le type de requête
    const path = url.pathname;
    
    // JSON dynamiques → Network First
    if (DYNAMIC_JSON.some(file => path.endsWith(file.replace('./', '')))) {
        event.respondWith(strategies.networkFirst(request));
        return;
    }
    
    // Images → Stale While Revalidate
    if (request.destination === 'image' || path.match(/\.(png|jpg|jpeg|gif|webp|svg)$/)) {
        event.respondWith(strategies.staleWhileRevalidate(request));
        return;
    }
    
    // Documents HTML → Network First avec fallback offline
    if (request.destination === 'document' || path.endsWith('.html')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    if (response.status === 200) {
                        const clone = response.clone();
                        caches.open(DYNAMIC_CACHE).then(cache => cache.put(request, clone));
                    }
                    return response;
                })
                .catch(() => {
                    return caches.match(request)
                        .then(cached => cached || caches.match('./offline.html'));
                })
        );
        return;
    }
    
    // CSS, JS, fonts → Cache First
    if (request.destination === 'style' || 
        request.destination === 'script' || 
        request.destination === 'font') {
        event.respondWith(strategies.cacheFirst(request));
        return;
    }
    
    // Par défaut → Cache First
    event.respondWith(strategies.cacheFirst(request));
});

// Gestion des messages du client
self.addEventListener('message', (event) => {
    if (event.data === 'skipWaiting') {
        self.skipWaiting();
    }
    
    if (event.data === 'getVersion') {
        event.ports[0].postMessage(CACHE_NAME);
    }
});

// Sync en arrière-plan (pour les analytics)
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-analytics') {
        event.waitUntil(syncAnalytics());
    }
});

async function syncAnalytics() {
    // Implémenter la synchronisation des analytics en attente
    log('🔄 Sync analytics...');
}

// Push notifications (préparation)
self.addEventListener('push', (event) => {
    const data = event.data?.json() || {};
    const options = {
        body: data.body || 'Nouveau pronostic disponible !',
        icon: './assets/images/icon-192x192.png',
        badge: './assets/images/icon-72x72.png',
        tag: data.tag || 'pronostic',
        requireInteraction: true,
        actions: [
            { action: 'open', title: 'Voir' },
            { action: 'close', title: 'Fermer' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    if (event.action === 'open' || !event.action) {
        event.waitUntil(
            clients.openWindow('./pronos.html')
        );
    }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});