/**
 * pwa.js - Enregistre le Service Worker pour la PWA
 * Permet le mode hors ligne et la mise en cache des ressources.
 */

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js')
            .then(registration => {
                console.log('ServiceWorker enregistré avec succès:', registration.scope);
            })
            .catch(error => {
                console.log('Échec de l\'enregistrement du ServiceWorker:', error);
            });
    });
}