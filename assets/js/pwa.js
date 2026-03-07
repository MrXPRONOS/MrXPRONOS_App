// pwa.js – Enregistrement du service worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const reg = await navigator.serviceWorker.register('./service-worker.js');
            console.log('✅ ServiceWorker enregistré:', reg.scope);
        } catch (err) {
            console.log('❌ ServiceWorker échec:', err);
        }
    });
}