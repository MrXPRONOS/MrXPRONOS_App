const CACHE_NAME = 'mr-xpronos-v1';
const urlsToCache = [
    './',
    './index.html',
    './pronos.html',
    './historique.html',
    './blog.html',
    './conseils.html',
    './infos.html',
    './contact.html',
    './article.html',
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
    './assets/images/888starz.png',
    './assets/images/whatsapp.png',
    './assets/images/telegram.png',
    './assets/images/instagram.png',
    './assets/images/facebook.png',
    './assets/images/youtube.png',
    './assets/images/phone.png',
    './assets/images/icon-192.png',
    './assets/images/icon-512.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
    );
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (url.pathname.endsWith('data.json')) {
        event.respondWith(
            fetch(event.request)
                .then(res => {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                    return res;
                })
                .catch(() => caches.match(event.request))
        );
    } else {
        event.respondWith(
            caches.match(event.request).then(res => res || fetch(event.request))
        );
    }
});