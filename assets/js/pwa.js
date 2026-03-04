/**
 * pwa.js - Enregistre le Service Worker et gère les mises à jour
 */

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // Utilisation d'un chemin relatif (./service-worker.js) pour que le navigateur cherche dans le même dossier que la page
        navigator.serviceWorker.register('./service-worker.js')
            .then(registration => {
                console.log('✅ ServiceWorker enregistré avec succès:', registration.scope);
                registration.onupdatefound = () => {
                    const installingWorker = registration.installing;
                    installingWorker.onstatechange = () => {
                        if (installingWorker.state === 'installed') {
                            if (navigator.serviceWorker.controller) {
                                console.log('Nouvelle version disponible, recharger pour mettre à jour.');
                            }
                        }
                    };
                };
            })
            .catch(error => {
                console.log('❌ Échec de l\'enregistrement du ServiceWorker:', error);
            });
    });

    // Rechargement automatique lors d'une mise à jour
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            window.location.reload();
        }
    });
}