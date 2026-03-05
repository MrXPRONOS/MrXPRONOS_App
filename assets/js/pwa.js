// assets/js/pwa.js
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

    // Ajout : confirmation que la PWA est prête pour le mode offline
    navigator.serviceWorker.ready.then(() => {
        console.log('🔋 PWA prête pour le mode offline avancé');
    });
}