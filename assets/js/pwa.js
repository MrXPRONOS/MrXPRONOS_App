// assets/js/pwa.js - Service Worker et gestion PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const reg = await navigator.serviceWorker.register('./service-worker.js');
            console.log('✅ ServiceWorker enregistré:', reg.scope);

            reg.onupdatefound = () => {
                const installing = reg.installing;
                installing.onstatechange = () => {
                    if (installing.state === 'installed') {
                        if (navigator.serviceWorker.controller) {
                            console.log('🚀 Nouvelle version disponible. Rechargez pour mettre à jour.');
                            // Optionnel : afficher une notification à l'utilisateur
                        } else {
                            console.log('📦 PWA installée pour la première fois.');
                        }
                    }
                };
            };
        } catch (err) {
            console.log('❌ ServiceWorker échec:', err);
        }
    });

    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            window.location.reload();
        }
    });

    navigator.serviceWorker.ready.then(() => {
        console.log('🔋 PWA prête pour le mode offline avancé');
    });
}