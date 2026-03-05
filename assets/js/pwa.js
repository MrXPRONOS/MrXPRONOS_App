// assets/js/pwa.js - Enregistrement du service worker et gestion des mises à jour

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./service-worker.js')
            .then(reg => {
                console.log('✅ ServiceWorker enregistré:', reg.scope);
                reg.onupdatefound = () => {
                    const installing = reg.installing;
                    installing.onstatechange = () => {
                        if (installing.state === 'installed') {
                            if (navigator.serviceWorker.controller) {
                                console.log('Nouvelle version disponible. Rechargez pour mettre à jour.');
                            }
                        }
                    };
                };
            })
            .catch(err => console.log('❌ ServiceWorker échec:', err));
    });

    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            window.location.reload();
        }
    });
}