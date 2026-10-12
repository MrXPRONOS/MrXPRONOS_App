// service-worker.js - Version corrigée et nettoyée

const VERSION = 'v65-history-mobile-refine-20261012';
const STATIC_CACHE = `mr-xpronos-static-${VERSION}`;
const DYNAMIC_CACHE = `mr-xpronos-dynamic-${VERSION}`;
const IMAGE_CACHE = `mr-xpronos-images-${VERSION}`;

const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';
const log = IS_DEV ? console.log.bind(console) : () => {};

const STATIC_ASSETS = [
    './',
    './index.html',
    './pronos.html',
    './live.html',
    './historique.html',
    './blog.html',
    './conseils.html',
    './infos.html',
    './bonus.html',
    './contact.html',
    './article.html',
    './conseil.html',
    './bookmakers.html',
    './offline.html',
    './manifest.json',
    './assets/css/style.css',
    './assets/css/home-premium.css',
    './assets/css/home-polish.css',
    './assets/css/pronos-premium.css',
    './assets/css/history-premium.css',
    './assets/css/blog-premium.css',
    './assets/css/conseils-premium.css',
    './assets/css/infos-premium.css',
    './assets/css/bonus-premium.css',
    './assets/css/live-premium.css',
    './assets/css/contact-premium.css',
    './assets/css/article-detail-premium.css',
    './assets/css/conseil-detail-premium.css',
    './assets/css/bookmakers-premium.css',
    './assets/css/mobile-nav-premium.css',
    './assets/js/main.js',
    './assets/js/home-premium.js',
    './assets/js/pwa.js',
    './assets/js/menu.js',
    './assets/js/back-to-top.js',
    './assets/images/default-logo.webp',
    './assets/images/1xbet.webp',
    './assets/images/1win.webp',
    './assets/images/betwinner.webp',
    './assets/images/melbet.webp',
    './assets/images/linebet.webp',
    './assets/images/betclic.webp',
    './assets/images/whatsapp.webp',
    './assets/images/telegram.webp',
    './assets/images/instagram.webp',
    './assets/images/facebook.webp',
    './assets/images/youtube.webp',
    './assets/images/threads.webp',
    './assets/images/mrxpronos-mark.png',
    './assets/images/blog-hero-ball.webp',
    './assets/images/pronostics-premium/hero-stadium.webp',
    './assets/images/bonus-premium/bonus-gift.webp',
    './assets/images/blog-premium/hero-blog.webp',
    './assets/images/conseils-premium/hero-conseils.webp',
    './assets/images/infos-premium/hero-infos.webp',
    './assets/images/mobile-premium/icon-home.webp',
    './assets/images/mobile-premium/icon-pronostics.webp',
    './assets/images/mobile-premium/icon-live.webp',
    './assets/images/mobile-premium/icon-history.webp',
    './assets/images/mobile-premium/icon-blog.webp',
    './assets/images/mobile-premium/icon-conseils.webp',
    './assets/images/mobile-premium/icon-infos.webp',
    './assets/images/mobile-premium/icon-bonus.webp',
    './assets/images/mobile-premium/icon-contact.webp',
    './assets/images/mobile-premium/icon-menu.webp',
    './assets/images/pronostics-premium/card-stadium.webp',
    './assets/images/pronostics-premium/icon-simple.webp',
    './assets/images/pronostics-premium/icon-pro.webp',
    './assets/images/pronostics-premium/icon-vip.webp',
    './assets/images/pronostics-premium/icon-share.webp',
    './assets/images/pronostics-premium/icon-search.webp',
    './assets/images/pronostics-premium/icon-calendar.webp',
    './assets/images/pronostics-premium/icon-chevron.webp',
    './assets/images/pronostics-premium/icon-ball.webp',
    './assets/images/live-premium/hero-live.webp',
    './assets/images/live-premium/hero-stadium.webp',
    './assets/images/live-premium/player-back.webp',
    './assets/images/live-premium/icon-stopwatch.webp',
    './assets/images/live-premium/icon-ball.webp',
    './assets/images/live-premium/icon-corner.webp',
    './assets/images/live-premium/icon-cards.webp',
    './assets/images/live-premium/icon-whistle.webp',
    './assets/images/live-premium/icon-target.webp',
    './assets/images/live-premium/icon-pie.webp',
    './assets/images/live-premium/icon-bars.webp',
    './assets/images/mrxpronos-horizontal.webp',
    './assets/images/mrxpronos-horizontal-compact.webp',
    './assets/images/mrxpronos-mark.webp',
    './assets/images/mrxpronos-logo-maquette.png',
    './assets/images/mrxpronos-horizontal.webp',
    './assets/images/mrxpronos-stacked.webp',
    './assets/images/mrxpronos-vertical.webp',
    './assets/images/mrxpronos-mark.png',
    './assets/images/favicon.png',
    './assets/images/apple-touch-icon.png',
    './assets/images/icon-72x72.png',
    './assets/images/icon-96x96.png',
    './assets/images/icon-128x128.png',
    './assets/images/icon-144x144.png',
    './assets/images/icon-192x192.png',
    './assets/images/icon-512x512.png'
];

const DYNAMIC_JSON = [
    './data.json',
    './articles.json',
    './conseils.json',
    './bonus.json',
    './infos.json',
    './bookmakers.json',
    './footnews.json',
    './testimonials.json'
];

self.addEventListener('install', (event) => {
    log('🔧 Installation Service Worker...');
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(async (cache) => {
                log('📦 Pré-cache des assets statiques...');
                const results = await Promise.allSettled(
                    STATIC_ASSETS.map(asset => cache.add(asset))
                );

                results.forEach((result, index) => {
                    if (result.status === 'rejected') {
                        log(`⚠️ Asset non mis en cache: ${STATIC_ASSETS[index]}`);
                    }
                });
            })
            .then(() => self.skipWaiting())
            .catch((err) => {
                log('❌ Erreur installation SW:', err);
            })
    );
});

self.addEventListener('activate', (event) => {
    log('🚀 Activation Service Worker...');
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter(name =>
                            name.startsWith('mr-xpronos-') &&
                            ![STATIC_CACHE, DYNAMIC_CACHE, IMAGE_CACHE].includes(name)
                        )
                        .map(name => {
                            log('🗑️ Suppression ancien cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => self.clients.claim())
    );
});

function stableGetRequest(request) {
    const stableUrl = new URL(request.url);
    stableUrl.search = '';
    return new Request(stableUrl.toString(), {
        method: 'GET',
        credentials: 'same-origin'
    });
}

const strategies = {
    cacheFirst: async (request, cacheName = STATIC_CACHE) => {
        const cache = await caches.open(cacheName);
        const stableRequest = stableGetRequest(request);
        const cached =
            await cache.match(stableRequest) ||
            await cache.match(request) ||
            await caches.match(stableRequest);

        if (cached) {
            fetch(request)
                .then((response) => {
                    if (response && response.ok) {
                        cache.put(stableRequest, response.clone());
                    }
                })
                .catch(() => {});
            return cached;
        }

        try {
            const response = await fetch(request);
            if (response && response.ok) {
                await cache.put(stableRequest, response.clone());
            }
            return response;
        } catch {
            return new Response('Offline', { status: 503 });
        }
    },

    networkFirst: async (request) => {
        const cache = await caches.open(DYNAMIC_CACHE);
        const stableUrl = new URL(request.url);
        stableUrl.search = '';
        const stableRequest = new Request(stableUrl.toString(), { method: 'GET' });

        try {
            const networkResponse = await fetch(request, { cache: 'no-store' });
            if (networkResponse && networkResponse.ok) {
                // Les paramètres ?t=... changent à chaque appel : on utilise une clé stable.
                await cache.put(stableRequest, networkResponse.clone());
                return networkResponse;
            }
            throw new Error(`HTTP ${networkResponse?.status || 0}`);
        } catch (error) {
            log('📴 Réseau indisponible, tentative cache stable:', stableUrl.toString(), error?.message || error);
        }

        const cached = await cache.match(stableRequest);
        if (cached) return cached;

        // Ne jamais fabriquer un faux data.json vide en HTTP 200.
        // main.js utilisera alors son dernier cache local non vide.
        return new Response(
            JSON.stringify({ error: 'offline', message: 'Donnée indisponible hors ligne' }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
            }
        );
    },

    staleWhileRevalidate: async (request) => {
        const cache = await caches.open(IMAGE_CACHE);
        const stableRequest = stableGetRequest(request);
        const cached =
            await cache.match(stableRequest) ||
            await cache.match(request) ||
            await caches.match(stableRequest);

        const fetchPromise = fetch(request)
            .then(async (response) => {
                if (response && response.ok) {
                    await cache.put(stableRequest, response.clone());
                }
                return response;
            })
            .catch(() => cached);

        return cached || fetchPromise || new Response('', { status: 503 });
    }
};

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    if (request.method !== 'GET') return;
    if (url.origin !== self.location.origin) return;

    const path = url.pathname;

    if (DYNAMIC_JSON.some(file => path.endsWith(file.replace('./', '')))) {
        event.respondWith(strategies.networkFirst(request));
        return;
    }

    if (request.destination === 'image' || path.match(/\.(png|jpg|jpeg|gif|webp|svg)$/i)) {
        event.respondWith(strategies.staleWhileRevalidate(request));
        return;
    }

    if (request.destination === 'document' || path.endsWith('.html')) {
        event.respondWith((async () => {
            const stableUrl = new URL(request.url);
            stableUrl.search = '';
            const stableRequest = new Request(stableUrl.toString(), {
                method: 'GET',
                headers: request.headers,
                credentials: 'same-origin'
            });

            try {
                const response = await fetch(request);
                if (response && response.ok) {
                    const clone = response.clone();
                    const cache = await caches.open(DYNAMIC_CACHE);
                    // Clé stable : article.html?slug=x et article.html partagent le même shell HTML.
                    await cache.put(stableRequest, clone);
                }
                return response;
            } catch (error) {
                log('📴 Navigation hors ligne:', stableUrl.pathname, error?.message || error);

                // 1. version exacte éventuellement visitée auparavant
                const exact = await caches.match(request);
                if (exact) return exact;

                // 2. shell HTML sans query string, pré-caché ou déjà visité
                const stable = await caches.match(stableRequest);
                if (stable) return stable;

                // 3. vraie page de secours
                const offline = await caches.match('./offline.html');
                return offline || new Response(
                    '<!doctype html><html lang="fr"><title>Hors ligne</title><body>Connexion indisponible.</body></html>',
                    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
                );
            }
        })());
        return;
    }

    if (
        request.destination === 'style' ||
        request.destination === 'script' ||
        request.destination === 'font'
    ) {
        event.respondWith(strategies.cacheFirst(request, STATIC_CACHE));
        return;
    }

    event.respondWith(strategies.cacheFirst(request, STATIC_CACHE));
});

self.addEventListener('message', (event) => {
    if (event.data === 'skipWaiting') {
        self.skipWaiting();
    }

    if (event.data === 'getVersion' && event.ports?.[0]) {
        event.ports[0].postMessage(VERSION);
    }
});

self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-analytics') {
        event.waitUntil(syncAnalytics());
    }
});

async function syncAnalytics() {
    log('🔄 Sync analytics...');
    return Promise.resolve();
}

self.addEventListener('push', (event) => {
    let data = {};
    try {
        data = event.data?.json() || {};
    } catch {
        data = {};
    }

    const options = {
        body: data.body || 'Nouveau pronostic disponible !',
        icon: './assets/images/icon-192x192.png',
        badge: './assets/images/favicon.png',
        tag: data.tag || 'pronostic',
        requireInteraction: true,
        data: { url: data.url || './pronos.html' },
        actions: [
            { action: 'open', title: 'Voir' },
            { action: 'close', title: 'Fermer' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'Mr XPRONOS', options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (event.action === 'close') return;

    const targetUrl = event.notification?.data?.url || './pronos.html';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if ('focus' in client) {
                    client.navigate?.(targetUrl);
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});